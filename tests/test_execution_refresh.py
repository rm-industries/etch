from unittest.mock import patch

from etchlib.execution.results import Status
from etchlib.facts.store import FactStore
from etchlib.providers.observations import FactRef, FactState
from etchlib.providers.plans import ApplyResult
from tests.execution_fixtures import ExecutionFixture


class ExecutionRefreshTests(ExecutionFixture):
    def test_establish_refresh_configure_without_repeating_completed_actions(
        self,
    ) -> None:
        self.staged()
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install", "configure"])
        self.assertEqual(self.fact.calls, ["tool", "tool"])
        self.assertEqual(self.action.calls, ["install", "configure"])
        self.assertEqual(report.actions[0].refreshed, (FactRef("demo", "tool"),))

    def test_refresh_marks_only_cached_facts_stale_before_lazy_consumption(
        self,
    ) -> None:
        self.staged()
        original = FactStore.invalidate
        states = []

        def invalidate(store: FactStore, ref: FactRef) -> None:
            original(store, ref)
            observation = store.peek(ref)
            assert observation is not None
            states.append(observation.state)
            self.assertEqual(self.fact.calls, ["tool"])

        with patch.object(FactStore, "invalidate", invalidate):
            report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(states, [FactState.STALE])

    def test_producer_failure_does_not_refresh_or_run_dependents(self) -> None:
        self.staged(fail=True)
        self.module("independent", actions=[{"establish": {"name": "independent"}}])
        with patch.object(
            FactStore,
            "invalidate",
            side_effect=AssertionError("invalidated after failure"),
        ):
            report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertEqual(self.action.applied, ["install"])
        self.assertEqual(
            [r.status for r in report.actions],
            [Status.FAILED, Status.BLOCKED, Status.BLOCKED],
        )
        self.assertEqual(self.fact.calls, ["tool"])

    def test_successful_producer_with_still_unavailable_fact_fails(self) -> None:
        self.staged()
        with (
            patch.dict(self.action.fact.values, {}, clear=True),
            patch.object(
                self.action,
                "apply",
                return_value=ApplyResult(True, "No tool installed"),
            ),
        ):
            report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertIn("no earlier producer/refresh path remains", report.error or "")
        self.assertEqual(
            [r.status for r in report.actions], [Status.CHANGED, Status.BLOCKED]
        )

    def test_unchanged_success_refreshes_but_skip_does_not(self) -> None:
        self.staged(changed=False)
        self.assertTrue(self.apply_repo().succeeded)
        self.assertEqual(self.fact.calls, ["tool", "tool"])
        self.fact.calls.clear()
        self.module(
            facts={"unused": {"state": "unused"}},
            actions=[
                {"establish": {"name": "skip", "skip": True}, "refresh": ["unused"]}
            ],
        )
        with patch.object(
            FactStore, "invalidate", side_effect=AssertionError("invalidated skip")
        ):
            report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(report.actions[0].status, Status.SKIPPED)
        self.assertEqual(self.fact.calls, [])

    def test_unused_refresh_is_never_gathered(self) -> None:
        self.module(
            facts={"unused": {"state": "unused"}},
            actions=[{"establish": {"name": "install"}, "refresh": ["unused"]}],
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded)
        self.assertEqual(self.fact.calls, [])
        self.assertIsNone(report.facts[FactRef("demo", "unused")])

    def test_new_fact_value_can_activate_previously_false_condition(self) -> None:
        self.fact.values["tool"] = "0.5"
        self.staged()
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install", "configure"])

    def test_provider_derived_cross_module_refresh(self) -> None:
        self.module(
            "producer",
            actions=[
                {
                    "establish": {
                        "name": "install",
                        "values": {"tool": "1"},
                        "refreshes": [["demo", "tool"]],
                    }
                }
            ],
        )
        self.module(
            facts={"tool": {"state": "tool"}},
            requires=["producer"],
            actions=[
                {
                    "establish": {"name": "configure"},
                    "when": {"fact": {"name": "tool", "matches": ">=1"}},
                }
            ],
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install", "configure"])

    def test_unrelated_cached_fact_is_not_invalidated(self) -> None:
        self.fact.values["stable"] = True
        self.module(
            facts={"tool": {"state": "tool"}, "stable": {"state": "stable"}},
            actions=[
                {
                    "establish": {"name": "install", "values": {"tool": "1"}},
                    "refresh": ["tool"],
                },
                {
                    "establish": {"name": "configure"},
                    "when": {
                        "fact": {"name": "tool", "matches": ">=1"},
                        "not": {"fact": {"name": "stable", "equals": False}},
                    },
                },
            ],
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.fact.calls, ["tool", "stable", "tool"])

    def test_deferred_condition_can_resolve_false(self) -> None:
        self.module(
            facts={"tool": {"state": "tool"}},
            actions=[
                {
                    "establish": {"name": "install", "values": {"tool": "0.5"}},
                    "refresh": ["tool"],
                },
                {"missing": {}, "when": {"fact": {"name": "tool", "matches": ">=1"}}},
            ],
        )
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install"])
        self.assertEqual(report.actions[1].status, Status.SKIPPED)
