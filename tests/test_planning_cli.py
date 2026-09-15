import contextlib
import sys
from unittest.mock import patch

from etchlib.graph.model import NodeId
from etchlib.providers.observations import FactRef, FactState
from tests.planning_fixtures import PlanningFixture
from tests.plugin_fixtures import write_plugin


class PlanningCliTests(PlanningFixture):
    def test_plan_never_applies_downloads_or_runs_actions(self) -> None:
        module = self.root / "modules/demo"
        module.mkdir(parents=True)
        script = module / "script"
        script.write_text("#!/bin/sh\ntouch changed\n")
        script.chmod(0o755)
        self.module(
            actions=[
                {"create": [str(self.root / "directory")]},
                {"link": {str(self.root / "link"): "script"}},
                {"shell": {"command": "touch changed", "sudo": True, "stdin": True}},
                {"script": {"path": "script"}},
                {"installer": {"url": "https://example.org/install"}},
            ]
        )
        with contextlib.ExitStack() as stack:
            for entry in self.registry.entries():
                if entry.kind == "action":
                    stack.enter_context(
                        patch.object(
                            entry.provider,
                            "apply",
                            side_effect=AssertionError("apply called"),
                        )
                    )
            stack.enter_context(
                patch(
                    "urllib.request.urlopen",
                    side_effect=AssertionError("download called"),
                )
            )
            stack.enter_context(
                patch("subprocess.run", side_effect=AssertionError("command ran"))
            )
            report = self.plan()
        self.assertEqual(len(report.plans), 5)
        self.assertTrue(report.plans[NodeId("demo", "action", 2)].elevated)
        for name in ("directory", "link", "changed", ".etch"):
            self.assertFalse((self.root / name).exists())
            self.assertFalse((module / name).exists())
        status, output, error = self.cli("--verbose")
        self.assertEqual(status, 0, error)
        for text in (
            "current: unknown",
            "network: yes",
            "network: unknown",
            "not authorized",
            "resources:",
            "core",
            "compatible",
            "interpreter: /bin/sh",
            "executable: /bin/sh",
            "Ownership:",
        ):
            self.assertIn(text, output)

    def test_requested_version_probe_is_allowed_and_observed(self) -> None:
        self.module(
            facts={"python": {"version": {"command": [sys.executable, "--version"]}}},
            actions=[
                {
                    "create": [str(self.root / "new")],
                    "when": {"fact": {"name": "python", "matches": ">=3.9"}},
                }
            ],
        )
        report = self.plan()
        result = report.facts[FactRef("demo", "python")]
        assert result is not None
        self.assertEqual(result.state, FactState.VALUE)
        self.assertFalse((self.root / "new").exists())

    def test_conflicts_fail_without_changes(self) -> None:
        self.module(
            actions=[
                {"link": {str(self.root / "target"): "module.conf"}},
                {"link": {str(self.root / "target"): "module.conf"}},
            ]
        )
        status, output, error = self.cli()
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn("conflict", error)
        self.assertFalse((self.root / "target").exists())

    def test_profile_and_explicit_selection(self) -> None:
        self.module("a")
        self.module("b")
        self.write(
            "profiles/dev.conf", {"schema_version": 1, "name": "dev", "modules": ["b"]}
        )
        status, output, error = self.cli("--profile", "dev")
        self.assertEqual(status, 0, error)
        self.assertIn("b: true", output)
        self.assertNotIn("a: true", output)
        self.assertIn("a: true", self.cli("a")[1])

    def test_plugin_compatibility_and_fact_origin(self) -> None:
        write_plugin(self.root / "vendor/example")
        self.write(
            "defaults.conf", {"schema_version": 1, "plugins": ["vendor/example"]}
        )
        self.module(
            facts={"plugin": {"example_fact": {}}},
            when={"fact": {"name": "plugin", "equals": "from plugin"}},
        )
        status, output, error = self.cli("-v")
        self.assertEqual(status, 0, error)
        self.assertIn("fact example_fact: plugin example 1.2.3", output)
        self.assertIn("API 1 compatible", output)
        path = self.root / "vendor/example/etch_plugin.py"
        path.write_text(path.read_text().replace('"api": 1', '"api": 999'))
        self.assertEqual(self.cli()[0], 1)
