"""Native CLI counts at planning snapshots and fresh mutation boundaries."""

import json
import os
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.planning.build import plan_repository
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.uv_fixtures import UvFixture


class UvEfficiencyTests(UvFixture):
    def test_empty_request_has_no_native_calls(self) -> None:
        plan = self.uv_plan(tools=[])
        self.assertEqual(plan.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(self.calls(), [])

    def test_repeated_actions_share_inventory_only_in_one_snapshot(self) -> None:
        self.state(tools={"tool": "1"})
        self.module(
            actions=[
                {"uv": {"command": str(self.command), "tools": ["tool"]}}
                for _ in range(3)
            ]
        )
        repo = load_repository(self.root)
        plan_repository(repo, self.registry)
        self.assertEqual(len(self.calls()), 3)
        plan_repository(repo, self.registry)
        self.assertEqual(len(self.calls()), 6)

    def test_cwd_environment_timeout_and_executable_separate_cached_targets(
        self,
    ) -> None:
        cache: dict[tuple[str, ...], Any] = {}
        context = replace(self.context, inspection_cache=cache)
        config = {"command": str(self.command), "tools": ["tool"]}
        plan_action(self.entry, config, context)
        plan_action(self.entry, config, context)
        self.assertEqual(len(self.calls()), 3)
        other = self.root / "other"
        other.mkdir()
        plan_action(self.entry, config, replace(context, module_root=other))
        plan_action(self.entry, {**config, "timeout": 10}, context)
        with patch.dict("os.environ", {"UV_TOOL_DIR": str(other)}):
            plan_action(self.entry, config, context)
        alias = self.bin / "uv-alias"
        alias.write_bytes(self.command.read_bytes())
        alias.chmod(0o755)
        plan_action(self.entry, {**config, "command": str(alias)}, context)
        self.assertEqual(len(self.calls()), 15)

    def test_apply_bypasses_stale_planning_cache_and_verifies_each_install(
        self,
    ) -> None:
        context = replace(self.context, inspection_cache={})
        plan = plan_action(
            self.entry, {"command": str(self.command), "tools": ["a", "b"]}, context
        )
        self.assertTrue(apply_action(self.entry, plan, context).changed)
        self.assertEqual(
            self.calls(),
            [
                ["tool", "dir"],
                ["tool", "dir", "--bin"],
                ["tool", "list"],
                ["tool", "dir"],
                ["tool", "dir", "--bin"],
                ["tool", "list"],
                ["tool", "install", "--no-python-downloads", "--", "a>=0"],
                ["tool", "list"],
                ["tool", "install", "--no-python-downloads", "--", "b>=0"],
                ["tool", "list"],
            ],
        )
        self.assertFalse(apply_action(self.entry, plan, context).changed)
        self.assertEqual(len(self.calls()), 13)
        self.assertEqual(self.installs(), [["a>=0"], ["b>=0"]])

    def test_partial_request_does_not_reinstall_satisfied_tool(self) -> None:
        self.state(tools={"a": "99"})
        apply_action(self.entry, self.uv_plan(tools=["a", "b"]), self.context)
        self.assertEqual(self.installs(), [["b>=0"]])
        self.assertEqual(len(self.calls()), 8)

    def test_child_environment_pins_tool_and_executable_directories(self) -> None:
        tools = self.root / "selected tools"
        executables = self.root / "selected bin"
        with patch.dict(
            os.environ, {"UV_TOOL_DIR": str(tools), "UV_TOOL_BIN_DIR": str(executables)}
        ):
            apply_action(self.entry, self.uv_plan(tools=["tool"]), self.context)
            self.assertEqual(os.environ["UV_TOOL_DIR"], str(tools))
        rows = [
            json.loads(line)
            for line in (self.bin / "calls.jsonl").read_text().splitlines()
        ]
        for row in rows:
            if row["args"][:2] in (["tool", "list"], ["tool", "install"]):
                self.assertEqual(row["tools"], str(tools))
                self.assertEqual(row["bin"], str(executables))

    def test_unrelated_execution_keeps_opaque_reinspection(self) -> None:
        self.module(
            actions=[
                {"create": ["unrelated"]},
                {"uv": {"command": str(self.command), "tools": ["tool"]}},
            ]
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(len(self.calls()), 11)
        self.assertEqual(self.installs(), [["tool>=0"]])
