"""Native inventory is shared only inside a snapshot; writes use fresh reads."""

from dataclasses import replace
from typing import Any
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.planning.build import plan_repository
from etchlib.providers.lifecycle import apply_action, plan_action
from tests.claude_fixtures import ClaudeFixture


class ClaudeEfficiencyTests(ClaudeFixture):
    def test_only_requested_categories_launch_inventory_commands(self) -> None:
        self.state(marketplaces=[self.market()], installed=[self.plugin()])
        for config, expected in (
            ({}, []),
            (
                {"marketplaces": ["owner/repo"]},
                [["plugin", "marketplace", "list", "--json"]],
            ),
            ({"plugins": ["hello@catalog"]}, [["plugin", "list", "--json"]]),
        ):
            before = len(self.calls())
            plan = self.claude_plan(**config)
            self.assertFalse(apply_action(self.entry, plan, self.context).changed)
            self.assertEqual(self.calls()[before:], expected + expected)

    def test_repeated_requests_share_inventory_only_in_one_snapshot(self) -> None:
        self.state(marketplaces=[self.market()], installed=[self.plugin()])
        config = {
            "command": str(self.command),
            "marketplaces": ["owner/repo"],
            "plugins": ["hello@catalog"],
        }
        self.module(actions=[{"claude": config} for _ in range(3)])
        repo = load_repository(self.root)
        plan_repository(repo, self.registry)
        self.assertEqual(len(self.calls()), 2)
        plan_repository(repo, self.registry)
        self.assertEqual(len(self.calls()), 4)

    def test_cache_separates_config_directory_cwd_executable_and_timeout(self) -> None:
        cache: dict[tuple[str, ...], Any] = {}
        context = replace(self.context, inspection_cache=cache)
        config = {"command": str(self.command), "plugins": ["hello@catalog"]}
        plan_action(self.entry, config, context)
        plan_action(self.entry, config, context)
        self.assertEqual(len(self.calls()), 1)
        other = self.root / "other"
        other.mkdir()
        plan_action(self.entry, config, replace(context, module_root=other))
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(other)}):
            plan_action(self.entry, config, context)
        plan_action(self.entry, {**config, "timeout": 10}, context)
        alias = self.bin / "other-claude"
        alias.write_bytes(self.command.read_bytes())
        alias.chmod(0o755)
        plan_action(self.entry, {**config, "command": str(alias)}, context)
        self.assertEqual(len(self.calls()), 5)

    def test_apply_rechecks_and_verifies_after_every_mutation(self) -> None:
        context = replace(self.context, inspection_cache={})
        plan = plan_action(
            self.entry,
            {
                "command": str(self.command),
                "marketplaces": ["owner/repo"],
                "plugins": ["hello@catalog"],
            },
            context,
        )
        self.assertTrue(apply_action(self.entry, plan, context).changed)
        self.assertEqual(
            self.calls(),
            [
                ["plugin", "marketplace", "list", "--json"],
                ["plugin", "list", "--json"],
                ["plugin", "marketplace", "list", "--json"],
                [
                    "plugin",
                    "marketplace",
                    "add",
                    "https://github.com/owner/repo.git",
                    "--scope",
                    "user",
                ],
                ["plugin", "marketplace", "list", "--json"],
                ["plugin", "list", "--json"],
                ["plugin", "install", "hello@catalog", "--scope", "user"],
                ["plugin", "list", "--json"],
            ],
        )
        self.assertFalse(apply_action(self.entry, plan, context).changed)
        self.assertEqual(len(self.calls()), 10)

    def test_unrelated_actions_preserve_engine_opaque_reinspection(self) -> None:
        config = {
            "command": str(self.command),
            "marketplaces": ["owner/repo"],
            "plugins": ["hello@catalog"],
        }
        self.module(actions=[{"create": ["unrelated"]}, {"claude": config}])
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(len(self.calls()), 10)
