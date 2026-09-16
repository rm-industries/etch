from dataclasses import replace
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.vscode_fixtures import VSCodeFixture


class VSCodeActionTests(VSCodeFixture):
    def test_explicit_bundle_and_provider_origin(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("vscode")
        self.module(
            actions=[
                {
                    "vscode": {
                        "command": str(self.code),
                        "extensions": ["ms-python.python"],
                    }
                }
            ]
        )
        status, output, error = self.cli("--verbose")
        self.assertEqual(status, 0, error)
        self.assertIn("plugin etch-vscode 0.1.0", output)
        self.assertIn("application:vscode", output)
        self.assertFalse(self.entry.origin.core)
        self.assertTrue(all(call[0] == "--list-extensions" for call in self.calls()))

    def test_normalization_missing_only_and_idempotence(self) -> None:
        self.state(extensions=["MS-Python.Python", "unlisted.keep", "MS-Python.Python"])
        requested = ["Zoo.Last", " ms-python.python ", "aaa.first", "ZOO.LAST"]
        plan = self.vscode_plan(requested)
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertTrue(plan.network)
        self.assertEqual(plan.resources, ("application:vscode",))
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        installs = [
            call[1] for call in self.calls() if call[0] == "--install-extension"
        ]
        self.assertEqual(installs, ["aaa.first", "zoo.last"])
        self.assertIn("unlisted.keep", self.current()["extensions"])
        self.assertEqual(self.vscode_plan(requested).status, PlanStatus.SKIP)
        self.assertEqual(requested[0], "Zoo.Last")

    def test_apply_rechecks_changes_since_planning(self) -> None:
        plan = self.vscode_plan(["ms-python.python"])
        self.state(extensions=["ms-python.python"])
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        self.assertFalse(any(call[0] == "--install-extension" for call in self.calls()))

    def test_extension_pack_dependencies_are_not_reinstalled(self) -> None:
        self.state(extensions=[], bundled={"aaa.pack": ["zzz.member"]})
        plan = self.vscode_plan(["aaa.pack", "zzz.member"])
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(
            [call[1] for call in self.calls() if call[0] == "--install-extension"],
            ["aaa.pack"],
        )

    def test_absent_command_fails_before_install(self) -> None:
        self.code.unlink()
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.vscode_plan(["ms-python.python"])
        self.assertEqual(self.calls(), [])

    def test_command_can_be_found_on_path_and_relative_to_module(self) -> None:
        with patch.dict("os.environ", {"PATH": str(self.bin)}):
            plan = plan_action(
                self.entry, {"extensions": [], "command": "fake code"}, self.context
            )
        self.assertEqual(plan.status, PlanStatus.SKIP)
        relative = "../../fake bin/fake code"
        plan = plan_action(
            self.entry, {"extensions": [], "command": relative}, self.context
        )
        self.assertEqual(plan.status, PlanStatus.SKIP)

    def test_profile_and_defaults_are_passed_as_single_arguments(self) -> None:
        context = replace(
            self.context,
            defaults={
                "vscode": {
                    "command": str(self.code),
                    "profile": "Work Space",
                    "timeout": 20,
                }
            },
        )
        plan = plan_action(self.entry, {"extensions": ["ms-python.python"]}, context)
        apply_action(self.entry, plan, context)
        self.assertTrue(all("--profile=Work Space" in call for call in self.calls()))

    def test_failures_stop_without_removal_or_retry(self) -> None:
        self.state(extensions=["unlisted.keep"], fail_extension="zzz.fail")
        with self.assertRaisesRegex(ProviderError, "status 8"):
            apply_action(
                self.entry, self.vscode_plan(["aaa.success", "zzz.fail"]), self.context
            )
        self.assertIn("aaa.success", self.current()["extensions"])
        self.assertIn("unlisted.keep", self.current()["extensions"])
        self.assertEqual(
            [call[1] for call in self.calls() if call[0] == "--install-extension"],
            ["aaa.success", "zzz.fail"],
        )

    def test_successful_exit_without_install_is_failure(self) -> None:
        self.state(extensions=[], pretend=True)
        with self.assertRaisesRegex(ProviderError, "remains missing"):
            apply_action(
                self.entry, self.vscode_plan(["ms-python.python"]), self.context
            )

    def test_invalid_ids_and_removal_options_are_rejected(self) -> None:
        for value in (
            "--help",
            "file.vsix",
            "../other.vsix",
            "ms.python@1",
            "bad id",
            "missingpublisher",
        ):
            with self.subTest(value=value), self.assertRaises(ProviderError):
                self.vscode_plan([value])
        with self.assertRaisesRegex(ProviderError, "removal is unsupported"):
            self.vscode_plan([], remove=["unlisted.keep"])
        self.assertEqual(self.calls(), [])

    def test_malformed_inventory_and_timeout_are_failures(self) -> None:
        self.state(output="unexpected output")
        with self.assertRaisesRegex(ProviderError, "invalid Marketplace"):
            self.vscode_plan(["ms-python.python"])
        self.state(sleep=1)
        with self.assertRaisesRegex(ProviderError, "timed out"):
            self.vscode_plan([], timeout=0.02)
