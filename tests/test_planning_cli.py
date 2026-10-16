import contextlib
import sys
from unittest.mock import patch

from etchlib.graph.model import NodeId
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import FactRef, FactState
from tests.planning_fixtures import PlanningFixture
from tests.plugin_fixtures import write_plugin


class PlanningCliTests(PlanningFixture):
    def test_reports_all_failures_and_later_changes_without_mutation(self) -> None:
        for name in ("first", "second"):
            (self.root / name).write_text("preserve")
        self.module("a", actions=[{"create": ["first"]}])
        self.module("b", actions=[{"create": ["second"]}, {"create": ["new"]}])
        for args in ((), ("--verbose",)):
            status, output, error = self.cli(*args)
            self.assertEqual(status, 1)
            for name in ("first", "second", "new"):
                self.assertIn(name, output + error)
            self.assertIn("Plan summary:", output)
            self.assertIn("ERROR", output)
            self.assertFalse((self.root / "new").exists())
            for name in ("first", "second"):
                self.assertEqual((self.root / name).read_text(), "preserve")
        with self.assertRaises(ProviderError):
            self.plan()
        for name in ("first", "second"):
            (self.root / name).unlink()
        self.assertEqual(self.cli()[0], 0)

    def test_reports_every_conflict_and_continues_after_failed_action(self) -> None:
        self.module(
            actions=[
                {"create": ["blocked"]},
                {"link": {"one": "module.conf", "two": "module.conf"}},
                {"link": {"one": "module.conf", "two": "module.conf"}},
                {"create": ["later"]},
            ]
        )
        (self.root / "blocked").write_text("preserve")
        status, output, error = self.cli()
        self.assertEqual(status, 1)
        self.assertIn("later", output)
        self.assertIn("blocked", output)
        self.assertEqual(output.count("destination conflict:"), 2)
        self.assertFalse((self.root / "one").exists())
        self.assertFalse((self.root / "later").exists())

    def test_reports_all_blocked_paths_in_one_action(self) -> None:
        for provider in ("link", "create"):
            for name in ("first", "second"):
                (self.root / name).write_text("preserve")
            config = (
                {"first": "module.conf", "second": "module.conf"}
                if provider == "link"
                else ["first", "second"]
            )
            self.module(actions=[{provider: config}])
            status, output, error = self.cli()
            self.assertEqual(status, 1)
            self.assertIn("first", output + error)
            self.assertIn("second", output + error)

    def test_dependency_failure_preserves_verbose_inspection_results(self) -> None:
        self.module(actions=[{"create": ["new"], "requires": ["missing"]}])
        status, output, error = self.cli("--verbose")
        self.assertEqual(status, 1)
        self.assertIn("Create directories: " + str(self.root / "new"), output)
        self.assertIn("Dependency checks incomplete", output)
        self.assertNotIn("no conflicts", output)

    def test_bad_condition_does_not_hide_other_modules(self) -> None:
        self.module("a", actions=[{"create": ["blocked"], "when": {"unknown": True}}])
        self.module("b", actions=[{"create": ["later"]}])
        status, output, error = self.cli()
        self.assertEqual(status, 1)
        self.assertIn("later", output)
        self.assertIn("ERROR", output)
        self.assertFalse((self.root / "later").exists())

    def test_reports_each_unresolved_condition(self) -> None:
        for name in ("a", "b"):
            self.module(
                name,
                facts={
                    "tool": {
                        "provider": "version",
                        "command": ["etch-missing-plan-test-tool"],
                    }
                },
                actions=[
                    {
                        "create": [name],
                        "when": {"fact": {"name": "tool", "matches": ">=1"}},
                    }
                ],
            )
        status, output, error = self.cli()
        self.assertEqual(status, 1)
        self.assertIn("a:action[0]", output)
        self.assertIn("b:action[0]", output)
        self.assertEqual(output.count("no earlier producer"), 2)

    def test_module_groups_and_multiline_links(self) -> None:
        self.module(
            actions=[
                {
                    "link": {
                        str(self.root / "one"): "module.conf",
                        str(self.root / "two"): "module.conf",
                    }
                },
                {"create": ["three"]},
                {"create": ["four"]},
            ]
        )
        status, output, error = self.cli()
        self.assertEqual(status, 0, error)
        self.assertEqual(output.count("demo:\n"), 1)
        self.assertIn(
            "  CHANGE — Link 2 paths:\n    - " + str(self.root / "one"), output
        )
        self.assertIn("\n    - " + str(self.root / "two"), output)
        self.assertNotIn("demo:action[", output)
        self.assertIn("demo:action[0]", self.cli("--verbose")[1])

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
        status, output, error = self.cli()
        self.assertEqual(status, 0, error)
        self.assertIn("Plan summary:", output)
        self.assertNotIn("current:", output)
        self.assertNotIn("Ownership:", output)
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
            facts={
                "python": {
                    "provider": "version",
                    "command": [sys.executable, "--version"],
                }
            },
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
        self.assertIn("Plan summary:", output)
        self.assertIn("conflict", output + error)
        self.assertFalse((self.root / "target").exists())

    def test_profile_and_explicit_selection(self) -> None:
        self.module("a")
        self.module("b")
        self.write(
            "profiles/dev.conf", {"schema_version": 1, "name": "dev", "modules": ["b"]}
        )
        status, output, error = self.cli("--profile", "dev")
        self.assertEqual(status, 0, error)
        self.assertIn("Here's what Etch found:\nb:", output)
        self.assertNotIn("a: true", output)
        self.assertIn("Here's what Etch found:\na:", self.cli("a")[1])

    def test_plugin_compatibility_and_fact_origin(self) -> None:
        write_plugin(self.root / "vendor/example")
        self.write(
            "defaults.conf", {"schema_version": 1, "plugins": ["vendor/example"]}
        )
        self.module(
            facts={"plugin": {"provider": "example_fact"}},
            when={"fact": {"name": "plugin", "equals": "from plugin"}},
        )
        status, output, error = self.cli("-v")
        self.assertEqual(status, 0, error)
        self.assertIn("fact example_fact: plugin example 1.2.3", output)
        self.assertIn("API 1 compatible", output)
        path = self.root / "vendor/example/etch_plugin.py"
        path.write_text(path.read_text().replace('"api": 1', '"api": 999'))
        self.assertEqual(self.cli()[0], 1)
