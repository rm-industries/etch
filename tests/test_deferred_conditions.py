import unittest
from unittest.mock import patch

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.module import select_module
from etchlib.conditions.results import ConditionError, Outcome
from etchlib.config import Module
from etchlib.providers.observations import FactResult, FactState
from tests.condition_fixtures import ConditionFixture


class DeferredTests(ConditionFixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ref = self.fact(
            "version", FactResult(FactState.UNAVAILABLE, reason="tool missing")
        )
        self.condition = {"fact": {"name": "version", "matches": ">=2.1"}}

    def test_required_unavailable_without_producer_is_error(self) -> None:
        with self.assertRaisesRegex(ConditionError, "no earlier producer/refresh path"):
            self.evaluator.evaluate(self.condition)

    def test_producer_evidence_allows_deferred_then_resolved(self) -> None:
        evaluator = Evaluator(self.store, self.context, {self.ref: "installer-action"})
        result = evaluator.evaluate(self.condition)
        self.assertEqual(result.outcome, Outcome.DEFERRED)
        self.assertEqual(result.waiting, (self.ref,))
        self.assertIn("installer-action", result.reasons[0])
        self.observations.values["version"] = FactResult(FactState.VALUE, "3.5a")
        self.store.invalidate(self.ref)
        # Once the producer has run, it is no longer an earlier pending producer.
        self.assertEqual(self.evaluator.evaluate(self.condition).outcome, Outcome.TRUE)

    def test_negation_preserves_deferral(self) -> None:
        evaluator = Evaluator(self.store, self.context, {self.ref: "installer"})
        self.assertEqual(
            evaluator.evaluate({"not": self.condition}).outcome, Outcome.DEFERRED
        )

    def test_stale_with_pending_producer_does_not_probe_early(self) -> None:
        self.store.get(self.ref)
        self.store.invalidate(self.ref)
        evaluator = Evaluator(self.store, self.context, {self.ref: "installer"})
        self.assertEqual(evaluator.evaluate(self.condition).outcome, Outcome.DEFERRED)
        self.assertEqual(len(self.observations.calls), 1)

    def test_false_and_true_or_discard_irrelevant_unresolved_facts(self) -> None:
        self.fact("flag", FactResult(FactState.VALUE, True))
        with patch("etchlib.facts.platform.platform.system", return_value="Linux"):
            self.assertEqual(
                self.evaluator.evaluate(dict(self.condition, os="macos")).outcome,
                Outcome.FALSE,
            )
        alternatives = {"fact": [self.condition["fact"], {"name": "flag"}]}
        self.assertEqual(self.evaluator.evaluate(alternatives).outcome, Outcome.TRUE)

    def test_inactive_module_skips_action_observations(self) -> None:
        module = Module(
            "demo",
            self.context.module_root,
            {
                "when": {"os": "macos"},
                "actions": [{"when": self.condition, "link": {}}],
            },
        )
        with patch("etchlib.facts.platform.platform.system", return_value="Linux"):
            selection = select_module(module, self.evaluator)
        self.assertEqual(selection.module.outcome, Outcome.FALSE)
        self.assertEqual(selection.actions[0].outcome, Outcome.FALSE)
        self.assertEqual(self.observations.calls, [])

    def test_deferred_module_keeps_all_actions_deferred(self) -> None:
        module = Module(
            "demo",
            self.context.module_root,
            {"when": self.condition, "actions": [{"link": {}}]},
        )
        selection = select_module(
            module, Evaluator(self.store, self.context, {self.ref: "installer"})
        )
        self.assertEqual(selection.module.outcome, Outcome.DEFERRED)
        self.assertEqual(selection.actions[0].outcome, Outcome.DEFERRED)

    def test_action_selection_preserves_order(self) -> None:
        self.fact("flag", FactResult(FactState.VALUE, False))
        module = Module(
            "demo",
            self.context.module_root,
            {
                "actions": [
                    {"link": {}},
                    {"when": {"fact": {"name": "flag"}}, "link": {}},
                ]
            },
        )
        selection = select_module(module, self.evaluator)
        self.assertEqual(
            tuple(r.outcome for r in selection.actions), (Outcome.TRUE, Outcome.FALSE)
        )

    def test_wrong_module_context_is_rejected(self) -> None:
        module = Module("other", self.context.module_root, {"actions": []})
        with self.assertRaisesRegex(ConditionError, "scoped to that module"):
            select_module(module, self.evaluator)
