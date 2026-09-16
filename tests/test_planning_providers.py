from typing import Any
from unittest.mock import patch

from etchlib.conditions.results import ConditionError, Outcome
from etchlib.graph.model import NodeId
from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactRef, FactState, Inspection
from etchlib.providers.plans import Plan, PlanStatus
from etchlib.providers.registry import Origin
from tests.planning_fixtures import PlanningFixture
from tests.provider_fixtures import MemoryAction, MemoryFact


class PlanningProviderTests(PlanningFixture):
    def test_provider_dependencies_facts_refresh_and_resources(self) -> None:
        action = MemoryAction()
        self.registry.register(
            Origin("example", "1"), actions=[action], facts=[MemoryFact()]
        )
        self.module("base")
        self.module(
            actions=[{"memory": {"value": "new"}}],
            facts={"installed": {"memory_value": {"value": "old"}}},
        )
        report = self.plan()
        key = NodeId("demo", "action", 0)
        self.assertEqual(action.calls, ["validate", "inspect", "plan"])
        self.assertIsNone(action.value)
        self.assertIn(NodeId("base", "finish"), report.graph.ancestors(key))
        self.assertIn(
            NodeId("demo", "refresh", 0, FactRef("demo", "installed")),
            report.graph.order(),
        )
        self.assertEqual(report.plans[key].resources, ("application:memory",))
        fact = report.facts[FactRef("demo", "installed")]
        assert fact is not None
        self.assertEqual(fact.value, "old")

    def test_cross_module_refresh_requires_dependency_path(self) -> None:
        action = MemoryAction()
        self.registry.register(Origin("example", "1"), actions=[action])
        self.module("producer", actions=[{"memory": {"value": "new"}}])
        refresh = Plan(PlanStatus.RUN, "Install", refresh=(FactRef("demo", "version"),))
        for requires in ([], ["producer"]):
            self.module(
                requires=requires,
                facts={
                    "version": {"version": {"command": [str(self.root / "absent")]}}
                },
                actions=[
                    {
                        "script": {"path": "absent"},
                        "when": {"fact": {"name": "version", "matches": ">=1"}},
                    }
                ],
            )
            with patch.object(action, "plan", return_value=refresh):
                if not requires:
                    with self.assertRaisesRegex(ConditionError, "no earlier producer"):
                        self.plan()
                else:
                    report = self.plan()
                    self.assertEqual(
                        report.selections["demo"].actions[0].outcome, Outcome.DEFERRED
                    )

    def test_provider_can_request_detached_lazy_facts(self) -> None:
        fact = MemoryFact()
        action = MemoryAction()
        self.registry.register(Origin("example", "1"), actions=[action], facts=[fact])
        self.module("base")
        self.module(
            actions=[{"memory": {"value": "new"}}],
            facts={"installed": {"memory_value": {"value": ["old"]}}},
        )
        original_inspect = action.inspect

        def inspect(config: Any, context: Context) -> Inspection:
            ref = FactRef("demo", "installed")
            first = context.facts[ref]
            first.value.append("local mutation")
            self.assertEqual(context.facts[ref].value, ["old"])
            return original_inspect(config, context)

        with (
            patch.object(fact, "gather", wraps=fact.gather) as gather,
            patch.object(action, "inspect", side_effect=inspect),
        ):
            report = self.plan()
        self.assertEqual(gather.call_count, 1)
        observation = report.facts[FactRef("demo", "installed")]
        assert observation is not None
        self.assertEqual(observation.state, FactState.VALUE)
