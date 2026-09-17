"""Exercise CLI diagnostics without allowing action execution."""

import contextlib
import io
from unittest.mock import patch

from etchlib.cli import main
from tests.planning_fixtures import PlanningFixture
from tests.plugin_fixtures import write_plugin


class DiagnosticTests(PlanningFixture):
    def invoke(self, command: str, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main([command, "--repo", str(self.root), *args])
        return status, out.getvalue(), err.getvalue()

    def test_facts_filter_and_scope_without_actions(self) -> None:
        self.module(
            "global",
            facts={"os": {"env": "ETCH_DIAGNOSTIC_VALUE"}},
            actions=[{"missing_provider": {}}],
        )
        self.module("excluded", facts={"bad": {"version": []}})
        self.write(
            "profiles/demo.conf",
            {"schema_version": 1, "name": "demo", "modules": ["global"]},
        )
        with patch.dict("os.environ", {"ETCH_DIAGNOSTIC_VALUE": "example"}):
            status, out, err = self.invoke("facts", "--profile", "demo")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("global/os: VALUE", out)
        self.assertIn("module/global/os: VALUE — 'example'", out)
        self.assertNotIn("excluded", out)
        self.assertEqual(self.invoke("facts", "global")[0], 0)

    def test_unused_probe_error_and_missing_command(self) -> None:
        self.module(
            facts={
                "bad": {"version": []},
                "tool": {"command": "etch-impossible-command-123456"},
            }
        )
        for command in ("facts", "doctor"):
            status, out, err = self.invoke(command)
            self.assertEqual((status, err), (1, ""))
            self.assertIn("module/demo/bad: ERROR", out)
            self.assertIn("module/demo/tool: UNAVAILABLE", out)
            self.assertIn("not found", out)

    def test_unavailable_is_warning_not_failure(self) -> None:
        self.module(facts={"tool": {"command": "etch-impossible-command-123456"}})
        status, out, err = self.invoke("doctor")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("Warning: module/demo/tool", out)
        self.assertIn("PATH", out)

    def test_doctor_never_applies_or_downloads(self) -> None:
        self.module(
            actions=[
                {"create": ["output"]},
                {"shell": {"command": "touch should-not-exist"}},
            ]
        )
        with patch(
            "etchlib.providers.lifecycle.apply_action",
            side_effect=AssertionError("applied"),
        ):
            status, out, err = self.invoke("doctor")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("Doctor OK", out)
        self.assertFalse((self.root / "output").exists())
        self.assertFalse((self.root / "modules/demo/should-not-exist").exists())

    def test_false_action_schema_and_missing_provider_are_checked(self) -> None:
        self.module(
            actions=[
                {"create": 123, "when": {"os": "impossible"}},
                {"not_registered": {}, "when": {"os": "impossible"}},
            ]
        )
        status, out, _ = self.invoke("doctor")
        self.assertEqual(status, 1)
        self.assertIn("validate failed", out)
        self.assertIn("missing action provider 'not_registered'", out)

    def test_dependency_and_claim_errors(self) -> None:
        self.module(requires=["missing"])
        self.assertIn("missing", self.invoke("doctor")[1])
        self.assertEqual(self.invoke("doctor")[0], 1)
        self.module(
            actions=[
                {"link": {"destination": "source"}},
                {"link": {"destination": "source"}},
            ]
        )
        (self.root / "modules/demo/source").write_text("example")
        status, out, _ = self.invoke("doctor")
        self.assertEqual(status, 1)
        self.assertIn("destination conflict", out)

    def test_broken_link_repair_is_reported_without_mutation(self) -> None:
        self.module(
            actions=[{"link": {"destination": {"path": "source", "relink": True}}}]
        )
        (self.root / "modules/demo/source").write_text("example")
        link = self.root / "destination"
        link.symlink_to("missing")
        status, out, _ = self.invoke("doctor")
        self.assertEqual(status, 0)
        self.assertIn("broken link", out)
        self.assertTrue(link.is_symlink())
        self.assertFalse(link.exists())

    def test_refresh_and_unresolved_facts(self) -> None:
        self.module(
            actions=[
                {
                    "create": ["output"],
                    "refresh": ["unknown"],
                    "when": {"os": "impossible"},
                }
            ]
        )
        status, out, _ = self.invoke("doctor")
        self.assertEqual(status, 1)
        self.assertIn("undeclared refresh fact", out)
        self.module(
            facts={"tool": {"command": "etch-impossible-command-123456"}},
            actions=[{"create": ["output"], "when": {"fact": {"name": "tool"}}}],
        )
        self.assertEqual(self.invoke("doctor")[0], 1)

    def test_plugin_facts_and_origins(self) -> None:
        write_plugin(self.root / "plugins/example")
        self.write(
            "defaults.conf", {"schema_version": 1, "plugins": ["plugins/example"]}
        )
        self.module(facts={"custom": {"example_fact": {}}})
        status, out, err = self.invoke("doctor")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("API 1 compatible", out)
        self.assertIn("plugin example 1.2.3", out)
        self.assertIn("module/demo/custom: VALUE — 'from plugin'", out)
        self.assertIn("from plugin", self.invoke("facts")[1])

    def test_unsupported_platform_and_runtime(self) -> None:
        self.module()
        with patch("platform.system", return_value="Windows"):
            status, out, _ = self.invoke("doctor")
        self.assertEqual(status, 1)
        self.assertIn("use Linux or macOS", out)
        with patch("sys.version_info", (3, 8)):
            status, out, _ = self.invoke("doctor")
        self.assertEqual(status, 1)
        self.assertIn("Python 3.9 or newer", out)

    def test_deferred_installer_is_explained_without_download(self) -> None:
        self.module(
            facts={"tool": {"command": "etch-impossible-command-123456"}},
            actions=[
                {
                    "installer": {"url": "https://example.invalid/install"},
                    "refresh": ["tool"],
                },
                {"create": ["output"], "when": {"fact": {"name": "tool"}}},
            ],
        )
        with patch("urllib.request.urlopen", side_effect=AssertionError("download")):
            status, out, err = self.invoke("doctor")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("Deferred:", out)
        self.assertIn("waiting for demo:action[0]", out)
        self.assertFalse((self.root / "output").exists())
