import unittest

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.config import Repository
from etchlib.graph.builder import build_graph
from etchlib.graph.model import FactLink, GraphError, NodeId
from etchlib.providers.observations import FactRef, FactResult, FactState
from etchlib.providers.plans import Plan, PlanStatus
from tests.condition_fixtures import ConditionFixture
from tests.graph_fixtures import inputs, module


class RefreshTests(ConditionFixture, unittest.TestCase):
    def graph_data(
        self,
    ) -> tuple[FactRef, Repository, dict[str, Selection], dict[NodeId, Plan]]:
        ref = FactRef("demo", "version")
        repository, selections, plans = inputs(
            module(
                "demo",
                [{"test": {}, "refresh": ["version"]}, {"test": {}}],
                facts={"version": {"version": {}}},
            )
        )
        selections["demo"] = Selection(
            Result(Outcome.TRUE),
            (Result(Outcome.TRUE), Result(Outcome.DEFERRED, (ref,))),
        )
        plans.pop(NodeId("demo", "action", 1))
        return ref, repository, selections, plans

    def test_establish_refresh_condition_chain(self) -> None:
        ref, repository, selections, plans = self.graph_data()
        self.fact("version", FactResult(FactState.UNAVAILABLE, reason="tool missing"))
        graph = build_graph(repository, selections, plans)
        consumer = NodeId("demo", "action", 1)
        evidence = graph.earlier_refresh(consumer)
        self.assertEqual(evidence, {ref: "demo:action[0]"})
        evaluator = Evaluator(self.store, self.context, evidence)
        self.assertEqual(
            evaluator.evaluate({"fact": {"name": "version", "matches": ">=2"}}).outcome,
            Outcome.DEFERRED,
        )

    def test_skipped_or_deferred_producer_cannot_supply_evidence(self) -> None:
        ref, repository, selections, plans = self.graph_data()
        producer, consumer = NodeId("demo", "action", 0), NodeId("demo", "action", 1)
        plans[producer] = Plan(PlanStatus.SKIP, "already installed")
        self.assertEqual(
            build_graph(repository, selections, plans).earlier_refresh(consumer), {}
        )
        plans[producer] = Plan(PlanStatus.CHANGE, "install")
        selections["demo"] = Selection(
            Result(Outcome.TRUE),
            (Result(Outcome.DEFERRED), Result(Outcome.DEFERRED, (ref,))),
        )
        self.assertEqual(
            build_graph(repository, selections, plans).earlier_refresh(consumer), {}
        )

    def test_unordered_producer_needs_explicit_fact_link(self) -> None:
        ref = FactRef("consumer", "version")
        repository, selections, plans = inputs(
            module("consumer", facts={"version": {"version": {}}}), module("installer")
        )
        consumer, producer = (
            NodeId("consumer", "action", 0),
            NodeId("installer", "action", 0),
        )
        plans[consumer] = Plan(PlanStatus.CHANGE, "configure", facts=(ref,))
        plans[producer] = Plan(PlanStatus.CHANGE, "install", refresh=(ref,))
        self.assertEqual(
            build_graph(repository, selections, plans).earlier_refresh(consumer), {}
        )
        graph = build_graph(
            repository, selections, plans, [FactLink(producer, consumer, ref)]
        )
        self.assertEqual(graph.earlier_refresh(consumer), {ref: str(producer)})

    def test_fact_link_cycle_is_rejected(self) -> None:
        ref, repository, selections, plans = self.graph_data()
        first, second = NodeId("demo", "action", 0), NodeId("demo", "action", 1)
        plans[first] = Plan(PlanStatus.CHANGE, "consume", facts=(ref,))
        plans[second] = Plan(PlanStatus.CHANGE, "produce", refresh=(ref,))
        with self.assertRaisesRegex(GraphError, "dependency cycle"):
            build_graph(repository, selections, plans, [FactLink(second, first, ref)])

    def test_unknown_refresh_is_invalid(self) -> None:
        with self.assertRaisesRegex(GraphError, "undeclared fact"):
            build_graph(*inputs(module("demo", [{"test": {}, "refresh": ["unknown"]}])))

    def test_module_gate_can_wait_on_external_producer(self) -> None:
        ref = FactRef("consumer", "version")
        repository, selections, plans = inputs(
            module("consumer", facts={"version": {"version": {}}}), module("installer")
        )
        gate, producer = NodeId("consumer", "start"), NodeId("installer", "action", 0)
        selections["consumer"] = Selection(
            Result(Outcome.DEFERRED, (ref,)), (Result(Outcome.DEFERRED, (ref,)),)
        )
        del plans[NodeId("consumer", "action", 0)]
        plans[producer] = Plan(PlanStatus.CHANGE, "install", refresh=(ref,))
        graph = build_graph(
            repository, selections, plans, [FactLink(producer, gate, ref)]
        )
        self.assertEqual(graph.earlier_refresh(gate), {ref: str(producer)})

    def test_producer_blocked_by_deferred_dependency_is_not_eligible(self) -> None:
        ref = FactRef("consumer", "version")
        repository, selections, plans = inputs(
            module("consumer", facts={"version": {"version": {}}}),
            module("installer", requires=["blocked"]),
            module("blocked"),
        )
        producer, consumer = (
            NodeId("installer", "action", 0),
            NodeId("consumer", "action", 0),
        )
        selections["blocked"] = Selection(
            Result(Outcome.DEFERRED), (Result(Outcome.DEFERRED),)
        )
        plans[producer] = Plan(PlanStatus.CHANGE, "install", refresh=(ref,))
        plans[consumer] = Plan(PlanStatus.CHANGE, "configure", facts=(ref,))
        graph = build_graph(
            repository, selections, plans, [FactLink(producer, consumer, ref)]
        )
        self.assertEqual(graph.earlier_refresh(consumer), {})

    def test_fact_link_requires_declared_producer_and_consumer(self) -> None:
        ref, repository, selections, plans = self.graph_data()
        producer, consumer = NodeId("demo", "action", 0), NodeId("demo", "action", 1)
        with self.assertRaisesRegex(GraphError, "does not consume"):
            build_graph(
                repository, selections, plans, [FactLink(consumer, producer, ref)]
            )
