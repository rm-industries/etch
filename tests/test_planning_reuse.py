"""Reusing intent must not freeze fact inputs or action eligibility."""

from tests.execution_fixtures import ExecutionFixture


class PlanningReuseTests(ExecutionFixture):
    def test_changed_fact_input_reinspects_reusable_action(self) -> None:
        self.fact.values["tool"] = "old"
        self.module(
            facts={"tool": {"provider": "state", "config": "tool"}},
            actions=[
                {
                    "establish": {"name": "install", "values": {"tool": "new"}},
                    "refresh": ["tool"],
                },
                {
                    "establish": {
                        "name": "consumer",
                        "reusable": True,
                        "facts": [["demo", "tool"]],
                    }
                },
            ],
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.calls, ["install", "consumer", "consumer"])
        self.assertEqual(self.fact.calls, ["tool", "tool"])

    def test_refreshed_condition_can_disable_reusable_action(self) -> None:
        self.fact.values["tool"] = True
        self.module(
            facts={"tool": {"provider": "state", "config": "tool"}},
            actions=[
                {
                    "establish": {"name": "install", "values": {"tool": False}},
                    "refresh": ["tool"],
                },
                {
                    "establish": {"name": "consumer", "reusable": True},
                    "when": {"fact": {"name": "tool", "equals": True}},
                },
            ],
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install"])

    def test_satisfied_and_opaque_plans_are_not_reused(self) -> None:
        self.module(
            actions=[
                {"establish": {"name": "change"}},
                {"establish": {"name": "satisfied", "reusable": True, "skip": True}},
                {"establish": {"name": "opaque", "reusable": True, "opaque": True}},
            ]
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(
            self.action.calls, ["change", "satisfied", "opaque", "satisfied", "opaque"]
        )
