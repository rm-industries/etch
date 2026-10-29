"""WinGet reconciliation through the independently loaded source bundle."""

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.observations import FactState
from etchlib.providers.plans import Plan, PlanStatus

ROOT = Path(__file__).resolve().parents[1]


class WingetTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.context = Context(self.root, self.root, "demo", {}, elevation_allowed=True)
        self.registry = load_plugins(ROOT, ["plugins/winget"], core_registry()).registry
        self.entry = self.registry.action("winget")
        self.packages = {"Git.Git", "Unrelated.App"}
        self.calls: list[tuple[str, ...]] = []
        self.output: Any = None
        self.failure = False
        self.fail_id = ""
        self.pretend = False
        self.dependencies: set[str] = set()
        self.executable = str(Path(sys.executable).resolve())
        self.locate = patch(
            "etchlib.providers.native.locate", return_value=self.executable
        ).start()
        self.addCleanup(patch.stopall)
        patch("etchlib.providers.native.run", side_effect=self.run_winget).start()

    def run_winget(self, executable: str, args: tuple[str, ...], **kwargs: Any) -> str:
        self.assertEqual(executable, self.executable)
        self.assertEqual(kwargs["cwd"], self.root)
        self.calls.append(args)
        if args[0] == "--version":
            return "v1.12.350\n"
        if args[0] == "export":
            output = self.output
            if output is None:
                output = {
                    "Sources": [
                        {
                            "SourceDetails": {"Name": args[args.index("--source") + 1]},
                            "Packages": [
                                {"PackageIdentifier": p} for p in sorted(self.packages)
                            ],
                        }
                    ]
                }
            Path(args[args.index("--output") + 1]).write_text(
                output if isinstance(output, str) else json.dumps(output),
                encoding="utf-8-sig",
            )
            return "localized warnings/progress are not inventory"
        self.assertEqual(args[0], "install")
        if self.failure or args[args.index("--id") + 1] == self.fail_id:
            raise ValueError("winget command exited with status 8")
        if not self.pretend:
            self.packages.add(args[args.index("--id") + 1])
            self.packages.update(self.dependencies)
        return "installed"

    def plan(self, **values: Any) -> Plan:
        return plan_action(self.entry, values, self.context)

    def installs(self) -> list[tuple[str, ...]]:
        return [args for args in self.calls if args[0] == "install"]

    def test_registration_and_presence_only_reconciliation(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("winget")
        plan = self.plan(
            packages=["Git.Git", "Microsoft.PowerShell", "Microsoft.PowerShell"]
        )
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertEqual(plan.resources, ("package-manager:winget",))
        self.assertTrue(plan.elevated)
        self.assertTrue(plan.network)
        self.assertTrue(plan.opaque)
        self.assertTrue(plan.reusable)
        self.assertEqual(self.installs(), [])
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(len(self.installs()), 1)
        args = self.installs()[0]
        self.assertEqual(args[args.index("--id") + 1], "Microsoft.PowerShell")
        for flag in ("--exact", "--no-upgrade", "--disable-interactivity", "--silent"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--source") + 1], "winget")
        self.assertIn("Unrelated.App", self.packages)
        second = self.plan(packages=["Git.Git", "Microsoft.PowerShell"])
        self.assertEqual(second.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, second, self.context).changed)
        self.assertEqual(len(self.installs()), 1)

    def test_invalid_requests_fail_before_commands(self) -> None:
        for name in (
            "--help",
            "",
            " Git.Git",
            "x y",
            "x;cmd",
            "x@1",
            "../x",
            "https://x",
            None,
        ):
            with self.subTest(name=name), self.assertRaises(ProviderError):
                self.plan(packages=[name])
        for config in (
            {},
            {"packages": "Git.Git"},
            {"packages": [], "upgrade": True},
            {"packages": [], "timeout": True},
            {"packages": [], "timeout": float("inf")},
            {"packages": [], "source": "--help"},
            {"packages": [], "command": "\n"},
        ):
            with self.subTest(config=config), self.assertRaises(ProviderError):
                self.plan(**config)
        self.assertEqual(self.calls, [])

    def test_empty_request_and_defaults(self) -> None:
        self.assertEqual(self.plan(packages=[]).status, PlanStatus.SKIP)
        self.assertEqual(self.calls, [])
        self.context = replace(
            self.context, defaults={"winget": {"timeout": 12, "source": "winget"}}
        )
        plan = self.plan(packages=["Git.Git"])
        self.assertEqual(plan.payload.target.timeout, 12)

    def test_bad_inventory_fails_before_install(self) -> None:
        for output in (
            "bad json",
            "[]",
            "{}",
            '{"Sources":null}',
            '{"Sources":[{}]}',
            '{"Sources":[{"Packages":null}]}',
            '{"Sources":[{"SourceDetails":{"Name":"other"},"Packages":[]}]}',
            '{"Sources":[{"SourceDetails":{"Name":"winget"},"Packages":[{}]}]}',
        ):
            self.output = output
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.plan(packages=["Git.Git"])
        self.assertEqual(self.installs(), [])
        self.output = {"Sources": []}
        self.assertEqual(self.plan(packages=["Git.Git"]).status, PlanStatus.CHANGE)

    def test_apply_refreshes_state_in_both_directions(self) -> None:
        plan = self.plan(packages=["Microsoft.PowerShell"])
        self.packages.add("Microsoft.PowerShell")
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        plan = self.plan(packages=["Git.Git"])
        self.packages.remove("Git.Git")
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)

    def test_snapshot_inventory_is_cached_but_apply_is_fresh(self) -> None:
        self.context = replace(self.context, inspection_cache={})
        self.plan(packages=["Git.Git"])
        plan = self.plan(packages=["Microsoft.PowerShell"])
        self.assertEqual(len(self.calls), 1)
        apply_action(self.entry, plan, self.context)
        self.assertEqual(
            [args[0] for args in self.calls], ["export", "export", "install", "export"]
        )
        for args in self.calls:
            if args[0] == "export":
                self.assertFalse(Path(args[args.index("--output") + 1]).exists())

    def test_failures_and_success_without_presence(self) -> None:
        plan = self.plan(packages=["A.App", "B.App"])
        self.failure = True
        with self.assertRaisesRegex(ProviderError, "status 8"):
            apply_action(self.entry, plan, self.context)
        self.failure = False
        self.packages.add("A.App")
        self.pretend = True
        with self.assertRaisesRegex(ProviderError, "remain missing"):
            apply_action(
                self.entry, self.plan(packages=["A.App", "B.App"]), self.context
            )
        self.assertEqual(self.installs()[-1][2], "B.App")
        self.pretend = False
        self.assertTrue(
            apply_action(
                self.entry, self.plan(packages=["A.App", "B.App"]), self.context
            ).changed
        )

    def test_executable_drift_and_missing_command(self) -> None:
        plan = self.plan(packages=["A.App"])
        self.locate.return_value = None
        with self.assertRaisesRegex(ProviderError, "changed since planning"):
            apply_action(self.entry, plan, self.context)
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.plan(packages=["A.App"])
        self.assertEqual(self.installs(), [])

    def test_facts(self) -> None:
        for kind, value in (
            ("command", self.executable),
            ("version", "1.12.350"),
            ("packages", ["Git.Git", "Unrelated.App"]),
        ):
            provider = self.registry.fact("winget." + kind).provider
            provider.validate({}, self.context)
            result = provider.gather({}, self.context)
            self.assertEqual(result.state, FactState.VALUE)
            self.assertEqual(result.value, value)
        self.locate.return_value = None
        for kind in ("command", "version", "packages"):
            result = self.registry.fact("winget." + kind).provider.gather(
                {}, self.context
            )
            self.assertEqual(result.state, FactState.UNAVAILABLE)

    def test_dependency_installed_by_previous_package_is_not_reinstalled(self) -> None:
        self.dependencies = {"B.App"}
        apply_action(self.entry, self.plan(packages=["A.App", "B.App"]), self.context)
        self.assertEqual([args[2] for args in self.installs()], ["A.App"])

    def test_unreadable_export_and_failed_inventory_are_not_empty(self) -> None:
        with patch("etchlib.providers.native.run", return_value=""):
            with self.assertRaisesRegex(ProviderError, "inventory"):
                self.plan(packages=["A.App"])
        with patch("etchlib.providers.native.run", side_effect=ValueError("status 5")):
            with self.assertRaisesRegex(ProviderError, "status 5"):
                self.plan(packages=["A.App"])
        self.assertEqual(self.installs(), [])

    def test_elevation_authorization_is_required_before_installing(self) -> None:
        plan = self.plan(packages=["A.App"])
        with self.assertRaisesRegex(ProviderError, "not been authorized"):
            apply_action(
                self.entry, plan, replace(self.context, elevation_allowed=False)
            )
        self.assertEqual(self.installs(), [])

    def test_partial_install_failure_reapply_only_installs_remaining_id(self) -> None:
        self.fail_id = "B.App"
        with self.assertRaisesRegex(ProviderError, "status 8"):
            apply_action(
                self.entry, self.plan(packages=["A.App", "B.App"]), self.context
            )
        self.assertIn("A.App", self.packages)
        self.assertNotIn("B.App", self.packages)
        self.fail_id = ""
        apply_action(self.entry, self.plan(packages=["A.App", "B.App"]), self.context)
        self.assertEqual(
            [args[2] for args in self.installs()], ["A.App", "B.App", "B.App"]
        )

    def test_oversized_inventory_is_rejected(self) -> None:
        module = type(self.entry.provider).__module__.rsplit(".", 1)[0] + ".cli"
        with patch(module + ".EXPORT_LIMIT", 10):
            with self.assertRaisesRegex(ProviderError, "exceeds"):
                self.plan(packages=["Git.Git"])
        self.assertEqual(self.installs(), [])

    def test_source_cache_isolation_and_facts_ignore_action_defaults(self) -> None:
        self.context = replace(
            self.context,
            inspection_cache={},
            defaults={"winget": {"source": "msstore"}},
        )
        self.plan(packages=["Git.Git"])
        self.plan(packages=["Git.Git"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][self.calls[0].index("--source") + 1], "msstore")
        provider = self.registry.fact("winget.packages").provider
        result = provider.gather({}, self.context)
        self.assertEqual(result.value, ["Git.Git", "Unrelated.App"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[1][self.calls[1].index("--source") + 1], "winget")
        result.value.append("mutated")
        self.assertEqual(
            provider.gather({}, self.context).value, ["Git.Git", "Unrelated.App"]
        )

    def test_source_names_are_case_insensitive(self) -> None:
        self.output = {
            "Sources": [{"SourceDetails": {"Name": "winget"}, "Packages": []}]
        }
        self.assertEqual(
            self.plan(packages=["Git.Git"], source="WinGet").status, PlanStatus.CHANGE
        )

    def test_failed_post_install_verification_stops_before_next_installer(self) -> None:
        self.pretend = True
        with self.assertRaisesRegex(ProviderError, "remain missing"):
            apply_action(
                self.entry, self.plan(packages=["A.App", "B.App"]), self.context
            )
        self.assertEqual([args[2] for args in self.installs()], ["A.App"])
