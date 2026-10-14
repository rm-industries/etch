"""Inspection work scales with actual execution, not satisfied actions."""

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from tests.execution_fixtures import ExecutionFixture


class ExecutionEfficiencyTests(ExecutionFixture):
    def test_satisfied_actions_are_inspected_once(self) -> None:
        names = ["ready-{}".format(index) for index in range(50)]
        self.module(
            actions=[{"establish": {"name": name, "skip": True}} for name in names]
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.calls, names)
        self.assertEqual(self.action.applied, [])
        self.assertTrue(
            all(action.status is Status.SKIPPED for action in report.actions)
        )

    def test_execution_still_reinspects_remaining_actions(self) -> None:
        self.module(
            actions=[
                {"establish": {"name": "ready", "skip": True}},
                {"establish": {"name": "change"}},
                {"establish": {"name": "remaining", "skip": True}},
            ]
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(
            self.action.calls, ["ready", "change", "remaining", "remaining"]
        )
        self.assertEqual(self.action.applied, ["change"])

    def test_parallel_satisfied_actions_are_inspected_once(self) -> None:
        names = ["ready-{}".format(index) for index in range(50)]
        self.module(
            actions=[{"establish": {"name": name, "skip": True}} for name in names]
        )
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.calls, names)
        self.assertEqual(self.action.applied, [])
