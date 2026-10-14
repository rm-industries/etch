"""Partial installs preserve independent work and explain dependency blocks."""

from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.providers.contracts import Context
from etchlib.providers.plans import ApplyResult, Plan
from tests.execution_fixtures import ExecutionFixture


class FailureContinuationTests(ExecutionFixture):
    def test_failures_block_both_dependency_types_and_continue_independent_work(
        self,
    ) -> None:
        for jobs in (1, 3):
            with self.subTest(jobs=jobs):
                self.module(
                    "a",
                    actions=[
                        {"establish": {"name": "before"}},
                        {"establish": {"name": "bad", "fail": True}},
                        {"establish": {"name": "later"}},
                    ],
                )
                self.module(
                    "b", requires=["a"], actions=[{"establish": {"name": "hard"}}]
                )
                self.module("c", after=["b"], actions=[{"establish": {"name": "soft"}}])
                self.module("d", actions=[{"establish": {"name": "free"}}])
                self.module(
                    "e", actions=[{"establish": {"name": "also-bad", "fail": True}}]
                )
                report = apply_repository(
                    load_repository(self.root), self.registry, jobs=jobs
                )
                outcomes = {str(item.node): item for item in report.actions}
                self.assertFalse(report.succeeded)
                self.assertEqual(outcomes["a:action[0]"].status, Status.CHANGED)
                self.assertEqual(outcomes["d:action[0]"].status, Status.CHANGED)
                self.assertEqual(outcomes["e:action[0]"].status, Status.FAILED)
                for key in ("a:action[2]", "b:action[0]", "c:action[0]"):
                    self.assertEqual(outcomes[key].status, Status.BLOCKED)
                    self.assertIn("a:action[1]", outcomes[key].description)

    def test_action_dependency_and_resource_sharing(self) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                self.module(
                    "a",
                    actions=[
                        {
                            "establish": {
                                "name": "bad",
                                "fail": True,
                                "resources": ["shared"],
                            }
                        }
                    ],
                )
                self.module(
                    "b", actions=[{"establish": {"name": "dependent"}, "after": ["a"]}]
                )
                self.module(
                    "c",
                    actions=[{"establish": {"name": "free", "resources": ["shared"]}}],
                )
                report = apply_repository(
                    load_repository(self.root), self.registry, jobs=jobs
                )
                outcomes = {item.node.module: item.status for item in report.actions}
                self.assertEqual(
                    outcomes,
                    {"a": Status.FAILED, "b": Status.BLOCKED, "c": Status.CHANGED},
                )

    def test_failed_partial_effect_is_reinspected_for_independent_work(self) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                self.fact.values["tool"] = "old"
                self.module(
                    "a",
                    facts={"tool": {"provider": "state", "config": "tool"}},
                    actions=[
                        {
                            "establish": {"name": "bad", "resources": ["shared"]},
                            "refresh": ["tool"],
                        }
                    ],
                )
                self.module(
                    "b",
                    actions=[
                        {
                            "establish": {
                                "name": "free",
                                "resources": ["shared"],
                                "facts": [["a", "tool"]],
                                "reusable": True,
                            }
                        }
                    ],
                )
                self.observed: list[str] = []

                def apply(plan: Plan, context: Context) -> ApplyResult:
                    if context.module_name == "a":
                        self.fact.values["tool"] = "partial"
                        raise ValueError("partially failed")
                    self.observed.append(
                        context.facts[
                            next(ref for ref in context.facts if ref.module == "a")
                        ].value
                    )
                    return ApplyResult(True, "independent")

                with patch.object(self.action, "apply", side_effect=apply):
                    report = apply_repository(
                        load_repository(self.root), self.registry, jobs=jobs
                    )
                self.assertFalse(report.succeeded)
                self.assertEqual(self.observed, ["partial"])
                self.assertTrue(
                    all(
                        not item.refreshed
                        for item in report.actions
                        if item.status is Status.FAILED
                    )
                )

    def test_failed_refresh_blocks_deferred_consumers_without_gathering_them(
        self,
    ) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                self.staged(fail=True)
                self.module("independent", actions=[{"establish": {"name": "free"}}])
                report = apply_repository(
                    load_repository(self.root), self.registry, jobs=jobs
                )
                outcomes = {
                    str(result.node): result.status for result in report.actions
                }
                self.assertEqual(outcomes["demo:action[1]"], Status.BLOCKED)
                self.assertEqual(outcomes["independent:action[0]"], Status.CHANGED)
                self.assertNotIn("configure", self.action.applied)

    def test_interruption_stops_new_work_even_when_independent(self) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                for name in ("a", "b", "c"):
                    self.module(
                        name,
                        actions=[{"establish": {"name": name, "resources": ["one"]}}],
                    )
                with patch.object(self.action, "apply", side_effect=KeyboardInterrupt):
                    report = apply_repository(
                        load_repository(self.root), self.registry, jobs=jobs
                    )
                self.assertEqual(
                    [result.status for result in report.actions],
                    [Status.FAILED, Status.BLOCKED, Status.BLOCKED],
                )
                self.assertIn("Interrupted", report.error or "")

    def test_rerun_completes_remaining_work_and_preserves_satisfied_actions(
        self,
    ) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                self.module(
                    "a",
                    actions=[
                        {"create": ["created-a-" + str(jobs)]},
                        {"establish": {"name": "bad", "fail": True}},
                    ],
                )
                self.module(
                    "b",
                    requires=["a"],
                    actions=[{"create": ["created-b-" + str(jobs)]}],
                )
                self.module("c", actions=[{"create": ["created-c-" + str(jobs)]}])
                first = apply_repository(
                    load_repository(self.root), self.registry, jobs=jobs
                )
                self.assertFalse(first.succeeded)
                self.assertTrue((self.root / ("created-a-" + str(jobs))).exists())
                self.assertTrue((self.root / ("created-c-" + str(jobs))).exists())
                self.assertFalse((self.root / ("created-b-" + str(jobs))).exists())
                self.module(
                    "a",
                    actions=[
                        {"create": ["created-a-" + str(jobs)]},
                        {"establish": {"name": "fixed"}},
                    ],
                )
                second = apply_repository(
                    load_repository(self.root), self.registry, jobs=jobs
                )
                self.assertTrue(second.succeeded, second.error)
                statuses = {
                    str(result.node): result.status for result in second.actions
                }
                self.assertEqual(statuses["a:action[0]"], Status.SKIPPED)
                self.assertEqual(statuses["c:action[0]"], Status.SKIPPED)
                self.assertTrue((self.root / ("created-b-" + str(jobs))).exists())
