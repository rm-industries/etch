"""Presence-only uv tool installs with explicit native targets and fresh reads."""

from dataclasses import replace
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers import native
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.uv_fixtures import UvFixture


class UvActionTests(UvFixture):
    def test_explicit_plugin_origin_and_plan_does_not_install(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("uv")
        self.module(actions=[{"uv": {"command": str(self.command), "tools": ["ruff"]}}])
        status, output, error = self.cli("-v")
        self.assertEqual(status, 0, error)
        self.assertIn("plugin etch-uv 0.1.0", output)
        self.assertIn("package-manager:uv", output)
        self.assertIn(str(self.bin / "tools"), output)
        self.assertEqual(
            self.calls(), [["tool", "dir"], ["tool", "dir", "--bin"], ["tool", "list"]]
        )
        self.assertEqual(self.current(), {})

    def test_install_canonical_missing_names_preserve_existing_and_project_files(
        self,
    ) -> None:
        self.state(tools={"ruff": "99.0.0", "unlisted": "3.0.0"})
        manifest = self.context.module_root / "pyproject.toml"
        lock = self.context.module_root / "uv.lock"
        manifest.write_text('[project]\nname="untouched"\nversion="1.0.0"\n')
        lock.write_text("untouched")
        plan = self.uv_plan(tools=["Ruff", "Foo.Bar", "foo_bar", "z-tool"])
        self.assertTrue(plan.network)
        self.assertTrue(plan.opaque)
        self.assertEqual(plan.resources, ("package-manager:uv",))
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(self.installs(), [["foo-bar>=0"], ["z-tool>=0"]])
        self.assertEqual(self.current()["tools"]["ruff"], "99.0.0")
        self.assertEqual(self.current()["tools"]["unlisted"], "3.0.0")
        self.assertIn('name="untouched"', manifest.read_text())
        self.assertEqual(lock.read_text(), "untouched")
        second = self.uv_plan(tools=["ruff", "foo-bar", "z-tool"])
        self.assertEqual(second.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, second, self.context).changed)
        self.assertEqual(len(self.installs()), 2)

    def test_invalid_requirements_options_and_timeout_fail_before_probes(self) -> None:
        for name in (
            "--help",
            "./tool",
            "../tool",
            "https://example.com/a",
            "git+ssh://repo",
            "tool==1",
            "tool>=1",
            "tool[extra]",
            "tool@url",
            "tool; python_version>'3'",
            "tool ",
            "_hidden",
            "tool-",
            "a/b",
            "",
        ):
            with self.subTest(name=name), self.assertRaises(ProviderError):
                self.uv_plan(tools=[name])
        for values in (
            {},
            {"tools": "ruff"},
            {"tools": [], "python": "3.12"},
            {"tools": [], "upgrade": True},
            {"tools": [], "timeout": True},
            {"tools": [], "timeout": float("nan")},
            {"tools": [], "command": "\n"},
        ):
            with self.subTest(values=values), self.assertRaises(ProviderError):
                self.uv_plan(**values)
        self.assertEqual(self.calls(), [])

    def test_malformed_or_incomplete_inventory_never_installs(self) -> None:
        for output in (
            "not inventory",
            "- orphan",
            "tool v1.0",
            "tool v1.0\n- ",
            "tool v1.0\n- tool\ntool v2.0\n- tool",
            "tool v1.0\n- tool\ngarbage",
            "tool v1.0\n- tool\n\x1b[0m",
        ):
            self.state(output=output)
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.uv_plan(tools=["tool"])
        self.state(tools={"tool": "1"}, list_status=7)
        with self.assertRaisesRegex(ProviderError, "status 7"):
            self.uv_plan(tools=["tool"])
        self.assertEqual(self.installs(), [])

    def test_uv_skipped_tool_warning_is_not_proof_of_absence(self) -> None:
        for output in ("", "other v1.0\n- other"):
            self.state(
                output=output,
                warning="warning: Ignoring malformed tool `tool` (run `uv tool uninstall tool` to remove)",
            )
            with (
                self.subTest(output=output),
                self.assertRaisesRegex(ProviderError, "inventory.*diagnostic"),
            ):
                self.uv_plan(tools=["tool"])
        self.assertEqual(self.installs(), [])

    def test_partial_failure_reapply_only_installs_remaining_tools(self) -> None:
        self.state(fail_tool="z")
        with self.assertRaisesRegex(ProviderError, "status 8"):
            apply_action(self.entry, self.uv_plan(tools=["a", "z"]), self.context)
        self.assertEqual(self.current()["tools"], {"a": "1.0.0"})
        self.state(tools=self.current()["tools"])
        apply_action(self.entry, self.uv_plan(tools=["a", "z"]), self.context)
        self.assertEqual(self.installs(), [["a>=0"], ["z>=0"], ["z>=0"]])

    def test_zero_exit_without_requested_tool_fails_verification(self) -> None:
        self.state(pretend=True)
        with self.assertRaisesRegex(ProviderError, "remains missing"):
            apply_action(self.entry, self.uv_plan(tools=["tool"]), self.context)

    def test_apply_rechecks_inventory_and_effective_directories(self) -> None:
        plan = self.uv_plan(tools=["tool"])
        self.state(tools={"tool": "2"})
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        satisfied = self.uv_plan(tools=["tool"])
        self.state()
        self.assertTrue(apply_action(self.entry, satisfied, self.context).changed)
        plan = self.uv_plan(tools=["other"])
        for state in (
            {"tools_dir": str(self.root / "different")},
            {"bin_dir": str(self.root / "different-bin")},
        ):
            self.state(**state)
            with (
                self.subTest(state=state),
                self.assertRaisesRegex(ProviderError, "directories changed"),
            ):
                apply_action(self.entry, plan, self.context)
        self.assertEqual(self.installs(), [["tool>=0"]])

    def test_executable_environment_drift_and_missing_cli(self) -> None:
        context = replace(
            self.context, defaults={"uv": {"command": str(self.command), "timeout": 10}}
        )
        plan = plan_action(self.entry, {"tools": ["tool"]}, context)
        self.assertEqual(plan.payload.target.timeout, 10)
        with patch.dict("os.environ", {"UV_TOOL_DIR": str(self.root / "other")}):
            with self.assertRaisesRegex(ProviderError, "environment changed"):
                apply_action(self.entry, plan, context)
        self.command.unlink()
        with self.assertRaisesRegex(ProviderError, "executable changed"):
            apply_action(self.entry, plan, context)
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.uv_plan(tools=["tool"])

    def test_invalid_directories_timeout_and_output_limits(self) -> None:
        for output in ("", "relative/tools", "/one\n/two"):
            self.state(dir_output=output)
            with (
                self.subTest(output=output),
                self.assertRaisesRegex(ProviderError, "directory"),
            ):
                self.uv_plan(tools=["tool"])
        self.state(sleep=1)
        with self.assertRaisesRegex(ProviderError, "timed out"):
            self.uv_plan(tools=["tool"], timeout=0.02)
        self.state(output="x" * 100)
        with patch.object(native, "OUTPUT_LIMIT", 64):
            with self.assertRaisesRegex(ProviderError, "output exceeds"):
                self.uv_plan(tools=["tool"])
