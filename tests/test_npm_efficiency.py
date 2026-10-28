"""Deterministic native-call counts and snapshot/mutation cache boundaries."""

from dataclasses import replace
from typing import Any
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.planning.build import plan_repository
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.npm_fixtures import NpmFixture


class NpmEfficiencyTests(NpmFixture):
    def test_empty_request_never_launches_native_commands(self) -> None:
        plan = self.npm_plan(packages=[])
        self.assertEqual(plan.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(self.calls(), [])

    def test_satisfied_repeated_actions_share_only_one_snapshot(self) -> None:
        self.state(packages={"tool": "1.0.0"})
        self.module(
            actions=[
                {"npm": {"command": str(self.npm), "packages": ["tool"]}}
                for _ in range(3)
            ]
        )
        repo = load_repository(self.root)
        plan_repository(repo, self.registry)
        self.assertEqual([args[0] for args in self.calls()], ["prefix", "ls"])
        plan_repository(repo, self.registry)
        self.assertEqual(
            [args[0] for args in self.calls()], ["prefix", "ls", "prefix", "ls"]
        )

    def test_distinct_effective_targets_do_not_share_cached_inventory(self) -> None:
        cache: dict[tuple[str, ...], Any] = {}
        context = replace(self.context, inspection_cache=cache)
        config = {"command": str(self.npm), "packages": ["tool"]}
        plan_action(self.entry, config, context)
        plan_action(self.entry, config, context)
        self.assertEqual(len(self.calls()), 2)
        other = self.root / "other"
        other.mkdir()
        (other / "lib").mkdir()
        plan_action(self.entry, config, replace(context, module_root=other))
        plan_action(self.entry, {**config, "timeout": 10}, context)
        plan_action(self.entry, {**config, "prefix": str(other)}, context)
        with patch.dict("os.environ", {"npm_config_prefix": str(other)}):
            plan_action(self.entry, config, context)
        alias = self.bin / "npm-alias"
        alias.write_bytes(self.npm.read_bytes())
        alias.chmod(0o755)
        plan_action(self.entry, {**config, "command": str(alias)}, context)
        self.assertEqual(len(self.calls()), 12)

    def test_apply_and_post_write_verification_bypass_cached_inventory(self) -> None:
        context = replace(self.context, inspection_cache={})
        plan = plan_action(
            self.entry, {"command": str(self.npm), "packages": ["a", "b"]}, context
        )
        self.assertTrue(apply_action(self.entry, plan, context).changed)
        self.assertEqual(
            [args[0] for args in self.calls()],
            ["prefix", "ls", "prefix", "ls", "install", "ls"],
        )
        self.assertFalse(apply_action(self.entry, plan, context).changed)
        self.assertEqual([args[0] for args in self.calls()][-2:], ["prefix", "ls"])
        self.assertEqual(self.installs(), [["a", "b"]])

    def test_partial_requests_batch_only_missing_names(self) -> None:
        self.state(packages={"a": "1"})
        apply_action(self.entry, self.npm_plan(packages=["a", "b", "c"]), self.context)
        self.assertEqual(self.installs(), [["b", "c"]])
        self.assertEqual(
            [args[0] for args in self.calls()],
            ["prefix", "ls", "prefix", "ls", "install", "ls"],
        )

    def test_unrelated_execution_keeps_opaque_planning_safety(self) -> None:
        self.module(
            actions=[
                {"create": ["unrelated"]},
                {"npm": {"command": str(self.npm), "packages": ["tool"]}},
            ]
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        # Script-capable npm installs are opaque: preserve the engine's reinspection rule.
        self.assertEqual(
            [args[0] for args in self.calls()],
            ["prefix", "ls", "prefix", "ls", "prefix", "ls", "install", "ls"],
        )
        self.assertEqual(self.installs(), [["tool"]])
