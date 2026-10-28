"""Presence-only global npm reconciliation, with no real package installation."""

from dataclasses import replace
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.npm_fixtures import NpmFixture


class NpmActionTests(NpmFixture):
    def test_registered_plugin_origin_and_plan_only_inventory(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("npm")
        self.module(actions=[{"npm": {"command": str(self.npm), "packages": ["tldr"]}}])
        status, output, error = self.cli("-v")
        self.assertEqual(status, 0, error)
        self.assertIn("plugin etch-npm 0.1.0", output)
        self.assertIn("package-manager:npm", output)
        self.assertIn(str(self.bin / "global"), output)
        self.assertEqual([args[0] for args in self.calls()], ["prefix", "ls"])
        self.assertEqual(self.current(), {})

    def test_install_sorted_missing_packages_and_preserve_existing_versions(
        self,
    ) -> None:
        self.state(packages={"tldr": "99.0.0", "unlisted": "3.0.0"})
        project = self.context.module_root / "package.json"
        project.write_text('{"private":true}')
        lock = self.context.module_root / "package-lock.json"
        lock.write_text("untouched")
        plan = self.npm_plan(packages=["tldr", "z-tool", "@scope/tool", "z-tool"])
        self.assertTrue(plan.reusable)
        self.assertTrue(plan.network)
        self.assertTrue(plan.opaque)
        self.assertEqual(plan.resources, ("package-manager:npm",))
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(self.installs(), [["@scope/tool", "z-tool"]])
        self.assertEqual(self.current()["packages"]["tldr"], "99.0.0")
        self.assertEqual(self.current()["packages"]["unlisted"], "3.0.0")
        self.assertEqual(project.read_text(), '{"private":true}')
        self.assertEqual(lock.read_text(), "untouched")
        second = self.npm_plan(packages=["@scope/tool", "tldr", "z-tool"])
        self.assertEqual(second.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, second, self.context).changed)
        self.assertEqual(len(self.installs()), 1)
        install = next(args for args in self.calls() if args[0] == "install")
        self.assertEqual(
            install[install.index("--") + 1 :], ["@scope/tool@*", "z-tool@*"]
        )
        self.assertIn("--dry-run=false", install)
        self.assertIn("--package-lock-only=false", install)
        self.assertIn("--package-lock=false", install)
        self.assertIn("--save=false", install)
        self.assertFalse(any(arg.startswith("--ignore-scripts") for arg in install))
        self.assertIn(
            "--link=false", next(args for args in self.calls() if args[0] == "ls")
        )
        self.assertIn(
            "--long=false", next(args for args in self.calls() if args[0] == "ls")
        )
        for args in self.calls():
            if args[0] in ("ls", "install"):
                self.assertIn("--global", args)
                self.assertIn("--prefix=" + str(self.bin / "global"), args)

    def test_invalid_names_and_options_fail_before_probing(self) -> None:
        for name in (
            "--help",
            "foo@1",
            "@scope/pkg@1",
            "https://example.org/pkg",
            "git+ssh://repo",
            "file:pkg",
            "a/b",
            "../pkg",
            "Foo",
            " space",
            "_hidden",
            ".hidden",
            "@scope/",
            "@/pkg",
            "npm:alias",
            "x;touch p",
            "x" * 215,
            "node_modules",
            "favicon.ico",
            "tool.tgz",
            "tool.tar.gz",
            "tool.tar",
        ):
            with self.subTest(name=name), self.assertRaises(ProviderError):
                self.npm_plan(packages=[name])
        for values in (
            {},
            {"packages": "tool"},
            {"packages": [], "upgrade": True},
            {"packages": [], "timeout": True},
            {"packages": [], "timeout": float("inf")},
            {"packages": [], "prefix": ""},
            {"packages": [], "command": "\n"},
        ):
            with self.subTest(values=values), self.assertRaises(ProviderError):
                self.npm_plan(**values)
        self.assertEqual(self.calls(), [])

    def test_missing_command_and_defaults(self) -> None:
        (self.context.module_root / "global tools/lib").mkdir(parents=True)
        context = replace(
            self.context,
            defaults={
                "npm": {
                    "command": str(self.npm),
                    "prefix": "./global tools",
                    "timeout": 10,
                }
            },
        )
        plan = plan_action(self.entry, {"packages": ["tool"]}, context)
        self.assertIn(str(self.context.module_root / "global tools"), plan.description)
        self.assertEqual(plan.payload.target.timeout, 10)
        self.npm.unlink()
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.npm_plan(packages=["tool"])

    def test_inventory_errors_do_not_trigger_installs(self) -> None:
        for output in (
            "not json",
            "[]",
            '{"dependencies":[]}',
            '{"dependencies":{"tool":{}}}',
            '{"dependencies":{"tool":{"version":"1","missing":true}}}',
            '{"dependencies":{"tool":{"version":"1","invalid":true}}}',
            '{"problems":["missing tool"]}',
            '{"error":{"code":"ELSPROBLEMS"}}',
            '{"error":{}}',
            '{"unrecognized":true}',
            '{"name":null}',
            '{"dependencies":null}',
            '{"dependencies":{"tool":"1.0.0"}}',
        ):
            self.state(output=output)
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.npm_plan(packages=["tool"])
        self.state(inventory_status=1, packages={"tool": "1.0.0"})
        with self.assertRaisesRegex(ProviderError, "status 1"):
            self.npm_plan(packages=["tool"])
        self.assertEqual(self.installs(), [])

    def test_partial_failure_reapply_only_installs_remaining_tools(self) -> None:
        self.state(partial_failure=True)
        with self.assertRaisesRegex(ProviderError, "status 8"):
            apply_action(self.entry, self.npm_plan(packages=["a", "b"]), self.context)
        self.assertEqual(self.current()["packages"], {"a": "1.0.0"})
        self.state(packages=self.current()["packages"])
        self.assertTrue(
            apply_action(
                self.entry, self.npm_plan(packages=["a", "b"]), self.context
            ).changed
        )
        self.assertEqual(self.installs(), [["a", "b"], ["b"]])

    def test_success_without_installed_packages_fails_verification(self) -> None:
        self.state(pretend=True)
        with self.assertRaisesRegex(ProviderError, "remain missing"):
            apply_action(self.entry, self.npm_plan(packages=["tool"]), self.context)

    def test_apply_rechecks_state_in_both_directions(self) -> None:
        plan = self.npm_plan(packages=["tool"])
        self.state(packages={"tool": "2"})
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        satisfied = self.npm_plan(packages=["tool"])
        self.state()
        self.assertTrue(apply_action(self.entry, satisfied, self.context).changed)
        self.assertEqual(self.installs(), [["tool"]])

    def test_target_drift_stops_before_writes(self) -> None:
        plan = self.npm_plan(packages=["tool"])
        self.state(prefix=str(self.root / "different-prefix"))
        with self.assertRaisesRegex(ProviderError, "prefix changed"):
            apply_action(self.entry, plan, self.context)
        self.state()
        with patch("os.environ", {"PATH": "/different-path"}):
            with self.assertRaisesRegex(ProviderError, "environment changed"):
                apply_action(self.entry, plan, self.context)
        self.npm.unlink()
        with self.assertRaisesRegex(ProviderError, "executable changed"):
            apply_action(self.entry, plan, self.context)
        self.assertEqual(self.installs(), [])

    def test_invalid_prefix_and_empty_inventory(self) -> None:
        for output in ("", "relative/prefix", "/prefix\n/other"):
            self.state(prefix_output=output)
            with (
                self.subTest(output=output),
                self.assertRaisesRegex(ProviderError, "prefix"),
            ):
                self.npm_plan(packages=["tool"])
        self.state(output="{}")
        self.assertEqual(self.npm_plan(packages=["tool"]).status, PlanStatus.CHANGE)
        self.state(output='{"resolved":"file:/empty-prefix/lib"}')
        self.assertEqual(self.npm_plan(packages=["tool"]).status, PlanStatus.CHANGE)

    def test_new_prefix_has_no_inventory_until_install_creates_it(self) -> None:
        prefix = self.context.module_root / "tool"
        plan = self.npm_plan(packages=["tool"], prefix=str(prefix))
        self.assertFalse(prefix.exists())
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        install = next(args for args in self.calls() if args[0] == "install")
        self.assertEqual(install[install.index("--") + 1 :], ["tool@*"])
        self.assertEqual(
            [args[0] for args in self.calls()], ["prefix", "prefix", "install", "ls"]
        )
