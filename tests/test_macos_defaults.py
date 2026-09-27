"""The reference preferences provider changes only declared keys."""

import platform
import plistlib
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.diagnostics.doctor import diagnose
from etchlib.diagnostics.render import render_doctor
from etchlib.planning.build import plan_repository
from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import apply_action, inspect_action
from etchlib.providers.observations import InspectionState
from etchlib.providers.plans import PlanStatus
from etchlib.providers.registry import Origin, Registry
from plugins.macos_defaults.action import MacOSDefaultsAction
from plugins.macos_defaults.cli import read_domain, write_key
from plugins.macos_defaults.schema import preferences


class MacOSDefaultsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.context = Context(root, root, "demo", {})
        registry = Registry()
        registry.register(Origin("test", "1"), actions=[MacOSDefaultsAction()])
        self.entry = registry.action("macos_defaults")
        self.config = {
            "domain": "com.example.EtchTests",
            "values": {
                "hidden": True,
                "count": 2,
                "ratio": 1.5,
                "text": "false",
            },
        }

    def test_reconciles_only_missing_or_different_typed_keys(self) -> None:
        current = {"unrelated": "keep", "hidden": 1, "text": False}
        writes = []

        def write(domain: str, key: str, value: object) -> None:
            writes.append(key)
            current[key] = value

        with (
            patch(
                "plugins.macos_defaults.action.platform.system", return_value="Darwin"
            ),
            patch(
                "plugins.macos_defaults.action.read_domain",
                side_effect=lambda _: dict(current),
            ),
            patch("plugins.macos_defaults.action.write_key", side_effect=write),
        ):
            observation, plan = inspect_action(self.entry, self.config, self.context)
            self.assertEqual(observation.state, InspectionState.CHANGE)
            self.assertEqual(plan.status, PlanStatus.CHANGE)
            self.assertIn("hidden (different)", plan.description)
            self.assertIn("count (missing)", plan.description)
            self.assertTrue(apply_action(self.entry, plan, self.context).changed)
            self.assertEqual(writes, ["hidden", "count", "ratio", "text"])
            self.assertEqual(current["unrelated"], "keep")

            _, second = inspect_action(self.entry, self.config, self.context)
            self.assertEqual(second.status, PlanStatus.SKIP)
            self.assertFalse(apply_action(self.entry, plan, self.context).changed)

            current["count"] = 3
            _, drift = inspect_action(self.entry, self.config, self.context)
            self.assertIn("count (different)", drift.description)
            self.assertNotIn("hidden (", drift.description)
            self.assertTrue(apply_action(self.entry, drift, self.context).changed)
            self.assertEqual(writes[-1], "count")

    def test_rejects_invalid_values_and_unsupported_platform(self) -> None:
        invalid: tuple[dict[str, object], ...] = (
            {"key": float("nan")},
            {"key": []},
            {"-key": "value"},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                preferences({"domain": "com.example.EtchTests", "values": values})
        with self.assertRaisesRegex(ValueError, "domain"):
            preferences({"domain": "../Preferences/app", "values": {"key": True}})
        with patch(
            "plugins.macos_defaults.action.platform.system", return_value="Linux"
        ):
            with self.assertRaisesRegex(Exception, "available only on macOS"):
                inspect_action(self.entry, self.config, self.context)

    def test_defaults_cli_preserves_plist_types_and_uses_typed_writes(self) -> None:
        calls = []

        def run(
            argv: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[bytes]:
            calls.append(argv)
            data = (
                plistlib.dumps({"flag": True, "number": 1, "text": "1"})
                if argv[1] == "export"
                else b""
            )
            return subprocess.CompletedProcess(argv, 0, data, b"")

        with patch("plugins.macos_defaults.cli.subprocess.run", side_effect=run):
            self.assertEqual(
                read_domain("com.example.EtchTests"),
                {"flag": True, "number": 1, "text": "1"},
            )
            write_key("com.example.EtchTests", "flag", True)
            write_key("com.example.EtchTests", "number", 1)
            write_key("com.example.EtchTests", "ratio", 1.5)
            write_key("com.example.EtchTests", "text", "1")
        self.assertEqual(
            [call[-2:] for call in calls[1:]],
            [["-bool", "true"], ["-int", "1"], ["-float", "1.5"], ["-string", "1"]],
        )

    def test_linux_guarded_module_skips_without_reading_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "examples/minimal",
                root,
                dirs_exist_ok=True,
            )
            (root / "modules/git/module.conf").write_text(
                repr(
                    {
                        "schema_version": 1,
                        "name": "git",
                        "when": {"os": "macos"},
                        "actions": [{"macos_defaults": self.config}],
                    }
                )
            )
            plugin = Path(__file__).resolve().parents[1] / "plugins/macos_defaults"
            registry = load_plugins(root, [str(plugin)], core_registry()).registry
            with (
                patch("platform.system", return_value="Linux"),
                patch(
                    "plugins.macos_defaults.action.read_domain",
                    side_effect=AssertionError("read"),
                ),
            ):
                report = plan_repository(load_repository(root), registry)
            self.assertEqual(report.plans, {})

    def test_doctor_reports_missing_keys_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "examples/minimal",
                root,
                dirs_exist_ok=True,
            )
            (root / "modules/git/module.conf").write_text(
                repr(
                    {
                        "schema_version": 1,
                        "name": "git",
                        "actions": [{"macos_defaults": self.config}],
                    }
                )
            )
            registry = core_registry()
            registry.register(Origin("test", "1"), actions=[MacOSDefaultsAction()])
            repository = load_repository(root)
            with (
                patch("platform.system", return_value="Darwin"),
                patch("plugins.macos_defaults.action.read_domain", return_value={}),
                patch(
                    "plugins.macos_defaults.action.write_key",
                    side_effect=AssertionError("write during doctor"),
                ),
            ):
                diagnosis = diagnose(repository, registry)
                output = render_doctor(repository, registry, (), diagnosis)
            self.assertEqual(diagnosis.errors, ())
            self.assertIn("Changes needed:", output)
            self.assertIn("hidden (missing)", output)


@unittest.skipUnless(platform.system() == "Darwin", "macOS preferences only")
class MacOSDefaultsIntegrationTests(unittest.TestCase):
    def test_disposable_domain_reconciles_without_replacing_unrelated_keys(
        self,
    ) -> None:
        domain = "com.rm-industries.etch-test." + uuid.uuid4().hex
        self.addCleanup(
            subprocess.run,
            ["/usr/bin/defaults", "delete", domain],
            capture_output=True,
            check=False,
        )
        context = Context(Path.cwd(), Path.cwd(), "test", {})
        registry = Registry()
        registry.register(Origin("test", "1"), actions=[MacOSDefaultsAction()])
        entry = registry.action("macos_defaults")
        write_key(domain, "unrelated", "keep")
        config = {
            "domain": domain,
            "values": {"hidden": True, "count": 2, "ratio": 1.5, "text": "false"},
        }
        _, first = inspect_action(entry, config, context)
        self.assertEqual(first.status, PlanStatus.CHANGE)
        self.assertTrue(apply_action(entry, first, context).changed)
        self.assertEqual(
            read_domain(domain),
            {
                "unrelated": "keep",
                "hidden": True,
                "count": 2,
                "ratio": 1.5,
                "text": "false",
            },
        )
        _, second = inspect_action(entry, config, context)
        self.assertEqual(second.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(entry, first, context).changed)
        write_key(domain, "count", 3)
        _, drift = inspect_action(entry, config, context)
        self.assertIn("count (different)", drift.description)
        self.assertNotIn("hidden (", drift.description)
        self.assertTrue(apply_action(entry, drift, context).changed)
        self.assertEqual(read_domain(domain)["count"], 2)
        write_key(domain, "text", False)
        _, typed_drift = inspect_action(entry, config, context)
        self.assertIn("text (different)", typed_drift.description)
