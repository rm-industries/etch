"""Count native calls while preserving fresh mutation and verification boundaries."""

from dataclasses import replace
from typing import Any
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.planning.build import plan_repository
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.codex_fixtures import CodexFixture


class CodexEfficiencyTests(CodexFixture):
    def satisfied(self) -> None:
        self.state(
            marketplaces=[
                {
                    "name": "catalog",
                    "marketplaceSource": {
                        "sourceType": "git",
                        "source": "https://github.com/owner/repo.git",
                    },
                }
            ],
            installed=[
                {
                    "pluginId": "hello@catalog",
                    "name": "hello",
                    "marketplaceName": "catalog",
                    "installed": True,
                    "enabled": False,
                }
            ],
        )

    def test_only_requested_inventory_is_read(self) -> None:
        self.satisfied()
        for config, expected in (
            ({}, []),
            (
                {"marketplaces": ["owner/repo"]},
                [["plugin", "marketplace", "list", "--json"]],
            ),
            ({"plugins": ["hello@catalog"]}, [["plugin", "list", "--json"]]),
        ):
            before = len(self.calls())
            plan = self.codex_plan(**config)
            self.assertEqual(plan.status, PlanStatus.SKIP)
            self.assertFalse(apply_action(self.entry, plan, self.context).changed)
            # Direct apply rechecks desired state; the engine skips a satisfied plan.
            self.assertEqual(self.calls()[before:], expected + expected)

    def test_satisfied_actions_share_inventory_only_within_their_snapshot(self) -> None:
        self.satisfied()
        config = {
            "command": str(self.code),
            "marketplaces": ["owner/repo"],
            "plugins": ["hello@catalog"],
        }
        self.module(actions=[{"codex": config} for _ in range(3)])
        repo = load_repository(self.root)
        plan_repository(repo, self.registry)
        self.assertEqual(len(self.calls()), 2)
        plan_repository(repo, self.registry)
        self.assertEqual(len(self.calls()), 4)

    def test_cache_respects_working_directory_home_target_and_timeout(self) -> None:
        self.satisfied()
        cache: dict[tuple[str, ...], Any] = {}
        context = replace(self.context, inspection_cache=cache)
        plan_action(
            self.entry,
            {"command": str(self.code), "plugins": ["hello@catalog"]},
            context,
        )
        plan_action(
            self.entry,
            {"command": str(self.code), "plugins": ["hello@catalog"]},
            context,
        )
        self.assertEqual(len(self.calls()), 1)
        other = self.root / "other"
        other.mkdir()
        plan_action(
            self.entry,
            {"command": str(self.code), "plugins": ["hello@catalog"]},
            replace(context, module_root=other),
        )
        with patch.dict(
            "os.environ", {"CODEX_HOME": str(self.root / "different-home")}
        ):
            plan_action(
                self.entry,
                {"command": str(self.code), "plugins": ["hello@catalog"]},
                context,
            )
        plan_action(
            self.entry,
            {"command": str(self.code), "timeout": 10, "plugins": ["hello@catalog"]},
            context,
        )
        alias = self.bin / "other-codex"
        alias.write_bytes(self.code.read_bytes())
        alias.chmod(0o755)
        plan_action(
            self.entry, {"command": str(alias), "plugins": ["hello@catalog"]}, context
        )
        self.assertEqual(len(self.calls()), 5)

    def test_apply_bypasses_planning_cache_and_verifies_every_install(self) -> None:
        context = replace(self.context, inspection_cache={})
        config = {
            "command": str(self.code),
            "marketplaces": ["owner/repo"],
            "plugins": ["hello@catalog"],
        }
        plan = plan_action(self.entry, config, context)
        result = apply_action(self.entry, plan, context)
        self.assertTrue(result.changed)
        self.assertEqual(len(self.calls()), 8)
        # Reusing the original missing-state cache must not reinstall anything.
        result = apply_action(self.entry, plan, context)
        self.assertFalse(result.changed)
        self.assertEqual(len(self.calls()), 10)

    def test_unrelated_execution_retains_changed_plan_intent(self) -> None:
        config = {
            "command": str(self.code),
            "marketplaces": ["owner/repo"],
            "plugins": ["hello@catalog"],
        }
        self.module(
            actions=[{"create": ["one"]}, {"create": ["two"]}, {"codex": config}]
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(len(self.calls()), 8)

    def test_apply_detects_state_removed_after_a_cached_satisfied_plan(self) -> None:
        self.satisfied()
        context = replace(self.context, inspection_cache={})
        config = {
            "command": str(self.code),
            "marketplaces": ["owner/repo"],
            "plugins": ["hello@catalog"],
        }
        plan = plan_action(self.entry, config, context)
        self.assertEqual(plan.status, PlanStatus.SKIP)
        self.state()
        self.assertTrue(apply_action(self.entry, plan, context).changed)
        self.assertEqual(len([call for call in self.calls() if "add" in call]), 2)
