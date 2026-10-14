"""Retry only recognizable temporary failures and only still-missing IDs."""

import importlib
import io
from contextlib import redirect_stderr
from dataclasses import replace
from unittest.mock import patch

from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from tests.vscode_fixtures import VSCodeFixture


class VSCodeRetryTests(VSCodeFixture):
    def setUp(self) -> None:
        super().setUp()
        self.retry = importlib.import_module(
            type(self.entry.provider).__module__.rsplit(".", 1)[0] + ".retry"
        )

    def test_transient_failure_recovers_and_preserves_successful_extensions(
        self,
    ) -> None:
        self.state(
            extensions=["unlisted.keep"],
            transient_failures=1,
            transient_extension="zzz.retry",
        )
        plan = self.vscode_plan(["aaa.success", "zzz.retry"], retries=2)
        output = io.StringIO()
        with patch.object(self.retry, "sleep") as sleep, redirect_stderr(output):
            result = apply_action(self.entry, plan, self.context)
        self.assertTrue(result.changed)
        self.assertEqual(
            [call[1] for call in self.calls() if call[0] == "--install-extension"],
            ["aaa.success", "zzz.retry", "zzz.retry"],
        )
        self.assertIn("unlisted.keep", self.current()["extensions"])
        self.assertIn("retry 1/2", output.getvalue())
        sleep.assert_called_once_with(1)

    def test_error_after_install_does_not_reinstall(self) -> None:
        self.state(extensions=[], transient_failures=1, install_on_failure=True)
        with patch.object(self.retry, "sleep") as sleep:
            result = apply_action(
                self.entry, self.vscode_plan(["pub.ext"], retries=2), self.context
            )
        self.assertTrue(result.changed)
        self.assertEqual(
            len([call for call in self.calls() if call[0] == "--install-extension"]), 1
        )
        sleep.assert_not_called()

    def test_exhaustion_is_bounded_and_returns_error(self) -> None:
        self.state(extensions=[], transient_failures=10)
        with patch.object(self.retry, "sleep") as sleep, redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(ProviderError, "503"):
                apply_action(
                    self.entry, self.vscode_plan(["pub.ext"], retries=3), self.context
                )
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4])
        self.assertEqual(
            len([call for call in self.calls() if call[0] == "--install-extension"]), 4
        )

    def test_default_and_unclassified_failures_do_not_retry(self) -> None:
        for retries, message in (
            (0, "Server returned 503"),
            (2, "Permission denied"),
            (2, "Permission denied; Server returned 503"),
            (2, "extension not found"),
            (2, "503 unrelated text"),
        ):
            with self.subTest(retries=retries, message=message):
                self.state(
                    extensions=[], transient_failures=1, transient_message=message
                )
                before = len(self.calls())
                with (
                    patch.object(self.retry, "sleep") as sleep,
                    self.assertRaises(ProviderError),
                ):
                    apply_action(
                        self.entry,
                        self.vscode_plan(["pub.ext"], retries=retries),
                        self.context,
                    )
                self.assertEqual(
                    len(
                        [
                            call
                            for call in self.calls()[before:]
                            if call[0] == "--install-extension"
                        ]
                    ),
                    1,
                )
                sleep.assert_not_called()

    def test_retry_bounds_are_validated_before_cli_calls(self) -> None:
        for value in (-1, 4, True, 1.5, "2"):
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.vscode_plan(["pub.ext"], retries=value)
        self.assertEqual(self.calls(), [])

    def test_defaults_can_enable_retries_and_an_action_can_disable_them(self) -> None:
        context = replace(self.context, defaults={"vscode": {"retries": 1}})
        self.state(extensions=[], transient_failures=1)
        config = {"command": str(self.code), "extensions": ["pub.ext"]}
        plan = plan_action(self.entry, config, context)
        with patch.object(self.retry, "sleep") as sleep, redirect_stderr(io.StringIO()):
            result = apply_action(self.entry, plan, context)
        self.assertTrue(result.changed)
        sleep.assert_called_once_with(1)
        self.state(extensions=[], transient_failures=1)
        plan = plan_action(self.entry, dict(config, retries=0), context)
        with (
            patch.object(self.retry, "sleep") as sleep,
            self.assertRaises(ProviderError),
        ):
            apply_action(self.entry, plan, context)
        sleep.assert_not_called()

    def test_other_recognized_service_statuses_recover(self) -> None:
        for status in (429, 502, 504):
            with self.subTest(status=status):
                self.state(
                    extensions=[],
                    transient_failures=1,
                    transient_message="Server returned " + str(status),
                )
                plan = self.vscode_plan(["pub.ext"], retries=1)
                with patch.object(self.retry, "sleep"), redirect_stderr(io.StringIO()):
                    result = apply_action(self.entry, plan, self.context)
                self.assertTrue(result.changed)
