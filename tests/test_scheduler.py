"""Event-controlled concurrency checks: no elapsed-time overlap assertions."""

import threading
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.providers.contracts import Context
from etchlib.providers.plans import ApplyResult, Plan
from etchlib.scheduling.resources import Resources
from tests.execution_fixtures import ExecutionFixture


class SchedulerTests(ExecutionFixture):
    def test_independent_actions_overlap(self) -> None:
        barrier = threading.Barrier(2)
        for name in ("a", "b"):
            self.module(name, actions=[{"establish": {"name": name}}])

        def apply(plan: Plan, context: Context) -> ApplyResult:
            barrier.wait(timeout=5)
            return ApplyResult(True, context.module_name)

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual([result.node.module for result in report.actions], ["a", "b"])

    def test_shared_resource_excludes_second_writer_but_not_unrelated_work(
        self,
    ) -> None:
        self.module(
            "a",
            actions=[
                {
                    "establish": {
                        "name": "first",
                        "resources": ["package-manager:example"],
                    }
                }
            ],
        )
        self.module(
            "b",
            actions=[
                {
                    "establish": {
                        "name": "second",
                        "resources": ["package-manager:example"],
                    }
                }
            ],
        )
        self.module("c", actions=[{"establish": {"name": "independent"}}])
        first = threading.Event()
        independent = threading.Event()
        sequence: list[str] = []

        def apply(plan: Plan, context: Context) -> ApplyResult:
            name = plan.payload["name"]
            if name == "first":
                sequence.append("first-start")
                first.set()
                if not independent.wait(5):
                    raise ValueError("independent action could not progress")
                sequence.append("first-end")
            elif name == "independent":
                if not first.wait(5):
                    raise ValueError("first writer never started")
                sequence.append("independent")
                independent.set()
            else:
                sequence.append("second")
            return ApplyResult(True, name)

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(load_repository(self.root), self.registry, jobs=3)
        self.assertTrue(report.succeeded, report.error)
        self.assertLess(sequence.index("first-end"), sequence.index("second"))
        self.assertLess(sequence.index("independent"), sequence.index("first-end"))

    def test_capacity_two_allows_two_holders_and_deduplicates_names(
        self,
    ) -> None:
        barrier = threading.Barrier(2)
        for name in ("a", "b"):
            self.module(
                name,
                actions=[
                    {"establish": {"name": name, "resources": ["network", "network"]}}
                ],
            )
        self.write(
            "defaults.conf",
            {
                "schema_version": 1,
                "execution": {"jobs": 2, "resources": {"network": 2}},
            },
        )

        def apply(plan: Plan, context: Context) -> ApplyResult:
            barrier.wait(timeout=5)
            return ApplyResult(True, "download")

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)

    def test_dependent_actions_do_not_overlap(self) -> None:
        self.module("a", actions=[{"establish": {"name": "first"}}])
        self.module("b", requires=["a"], actions=[{"establish": {"name": "second"}}])
        report = apply_repository(load_repository(self.root), self.registry, jobs=3)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["first", "second"])

    def test_failure_stops_admission_and_drains_inflight_results(self) -> None:
        failure_collected = threading.Event()
        self.module(
            "a",
            actions=[
                {"establish": {"name": "fail", "resources": ["failure"]}},
                {"establish": {"name": "dependent"}},
            ],
        )
        self.module("b", actions=[{"establish": {"name": "running"}}])
        self.module("c", actions=[{"establish": {"name": "pending"}}])

        def apply(plan: Plan, context: Context) -> ApplyResult:
            if plan.payload["name"] == "fail":
                raise ValueError("controlled failure")
            if not failure_collected.wait(5):
                raise ValueError("failure was not collected")
            return ApplyResult(True, "finished inflight")

        original_release = Resources.release

        def release(resources: Resources, names: frozenset[str]) -> None:
            original_release(resources, names)
            if "failure" in names:
                failure_collected.set()

        with (
            patch.object(self.action, "apply", side_effect=apply),
            patch.object(Resources, "release", release),
        ):
            report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertFalse(report.succeeded)
        outcomes = {str(result.node): result.status for result in report.actions}
        self.assertEqual(outcomes["a:action[0]"], Status.FAILED)
        self.assertEqual(outcomes["b:action[0]"], Status.CHANGED)
        self.assertEqual(outcomes["a:action[1]"], Status.BLOCKED)
        self.assertEqual(outcomes["c:action[0]"], Status.BLOCKED)

    def test_refresh_and_configuration_progress_while_unrelated_action_runs(
        self,
    ) -> None:
        self.staged()
        self.module("long", actions=[{"establish": {"name": "long"}}])
        long_started, configured = threading.Event(), threading.Event()
        original = self.action.apply

        def apply(plan: Plan, context: Context) -> ApplyResult:
            name = plan.payload["name"]
            if name == "install":
                if not long_started.wait(5):
                    raise ValueError("unrelated action not started")
            elif name == "long":
                long_started.set()
                if not configured.wait(5):
                    raise ValueError("refresh blocked behind unrelated work")
            result = original(plan, context)
            if name == "configure":
                configured.set()
            return result

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.fact.calls, ["tool", "tool"])
        self.assertLess(
            self.action.applied.index("configure"), self.action.applied.index("long")
        )

    def test_fact_consumers_wait_for_writer_and_receive_fresh_snapshot(self) -> None:
        from etchlib.providers.observations import FactRef

        self.fact.values["tool"] = "old"
        self.module(
            "a",
            facts={"tool": {"state": "tool"}},
            actions=[
                {
                    "establish": {"name": "writer", "values": {"tool": "new"}},
                    "refresh": ["tool"],
                }
            ],
        )
        self.module(
            "b", actions=[{"establish": {"name": "reader", "facts": [["a", "tool"]]}}]
        )
        self.module("c", actions=[{"establish": {"name": "long"}}])
        started, consumed = threading.Event(), threading.Event()
        original = self.action.apply

        def apply(plan: Plan, context: Context) -> ApplyResult:
            name = plan.payload["name"]
            if name == "writer" and not started.wait(5):
                raise ValueError("long action never started")
            if name == "reader":
                self.assertEqual(context.facts[FactRef("a", "tool")].value, "new")
                consumed.set()
            if name == "long":
                started.set()
                if not consumed.wait(5):
                    raise ValueError("reader blocked behind unrelated action")
            return original(plan, context)

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(load_repository(self.root), self.registry, jobs=3)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.fact.calls, ["tool", "tool"])

    def test_interactive_actions_share_terminal_even_with_different_resources(
        self,
    ) -> None:
        self.module("a", actions=[{"establish": {"name": "sudo", "sudo": True}}])
        self.module(
            "b",
            actions=[
                {"establish": {"name": "stdin", "resources": ["stdin-interactive"]}}
            ],
        )
        self.module("c", actions=[{"establish": {"name": "independent"}}])
        overlap = threading.Barrier(2)
        sudo_finished = threading.Event()

        def apply(plan: Plan, context: Context) -> ApplyResult:
            name = plan.payload["name"]
            if name in ("sudo", "independent"):
                overlap.wait(timeout=5)
            if name == "sudo":
                self.assertTrue(context.elevation_allowed)
                sudo_finished.set()
            if name == "stdin":
                self.assertTrue(sudo_finished.is_set())
            return ApplyResult(True, name)

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(
                load_repository(self.root), self.registry, jobs=3, allow_sudo=True
            )
        self.assertTrue(report.succeeded, report.error)
