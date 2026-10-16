"""Static cross-platform declarations and active host restrictions stay separate."""

from typing import Any
from unittest.mock import patch

from etchlib.config_validate import validate_repository
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import apply_action, plan_action
from tests.planning_fixtures import PlanningFixture


class InstallerValidationTests(PlanningFixture):
    def test_shared_consumer_validates_module_and_action_guards_on_every_host(
        self,
    ) -> None:
        actions = []
        for os_name, shell in (
            ("linux", "/bin/bash"),
            ("macos", "/bin/sh"),
            ("windows", "powershell.exe"),
        ):
            installer = {"url": "https://example.com/install", "shell": shell}
            self.module(
                os_name, when={"os": os_name}, actions=[{"installer": installer}]
            )
            actions.append({"installer": installer, "when": {"os": os_name}})
        self.module("mixed", actions=actions)
        for host in ("Windows", "Darwin", "Linux"):
            with (
                self.subTest(host=host),
                patch("platform.system", return_value=host),
                patch("etchlib.providers.installer.provider.checked") as checked,
            ):
                validate_repository(self.root)
                checked.assert_not_called()

    def test_inactive_declarations_still_reject_bad_schema_and_conditions(self) -> None:
        options: dict[str, Any]
        for options in (
            {"unknown": True},
            {"shell": 123},
            {"args": "--yes"},
            {"timeout": False},
            {"env": []},
            {"url": "http://example.com/install"},
        ):
            for guard in ("module", "action"):
                action: dict[str, Any] = {
                    "installer": {
                        "url": "https://example.com/install",
                        "shell": "/bin/bash",
                        **options,
                    }
                }
                if guard == "action":
                    action["when"] = {"os": "linux"}
                self.module(
                    "demo",
                    actions=[action],
                    **({"when": {"os": "linux"}} if guard == "module" else {}),
                )
                with (
                    self.subTest(options=options, guard=guard),
                    patch("platform.system", return_value="Windows"),
                    self.assertRaises(ValueError),
                ):
                    validate_repository(self.root)
        for guard in ("module", "action"):
            action = {"installer": {"url": "https://example.com/install"}}
            if guard == "action":
                action["when"] = {"unknown": True}
            self.module(
                "demo",
                actions=[action],
                **({"when": {"unknown": True}} if guard == "module" else {}),
            )
            with self.subTest(guard=guard), self.assertRaises(ValueError):
                validate_repository(self.root)

    def test_active_unix_installer_is_rejected_before_checks_or_download_on_windows(
        self,
    ) -> None:
        self.module()
        context = Context(self.root, self.root / "modules/demo", "demo", {})
        entry = self.registry.action("installer")
        config = {"url": "https://example.com/install", "shell": "/bin/bash"}
        with patch("platform.system", return_value="Linux"):
            prior_plan = plan_action(entry, config, context)
        with (
            patch("platform.system", return_value="Windows"),
            patch("etchlib.providers.installer.provider.checked") as checked,
            patch("etchlib.providers.installer.provider.download") as download,
            patch("etchlib.providers.installer.provider.run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "PowerShell scripts only"):
                plan_action(entry, config, context)
            with self.assertRaisesRegex(ValueError, "PowerShell scripts only"):
                apply_action(entry, prior_plan, context)
            checked.assert_not_called()
            download.assert_not_called()
            run.assert_not_called()
