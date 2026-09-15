import unittest

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.graph.builder import build_graph
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import GraphError, Node, NodeId
from etchlib.providers.plans import Plan, PlanStatus
from tests.graph_fixtures import inputs, module


class GraphTests(unittest.TestCase):
    def test_stable_profile_order_and_action_order(self):
        data = inputs(module("zsh", [{"test": {}}, {"test": {}}]), module("git"))
        graph = build_graph(*data)
        actions = [key for key in graph.order() if key.kind == "action"]
        self.assertEqual(
            actions,
            [
                NodeId("zsh", "action", 0),
                NodeId("zsh", "action", 1),
                NodeId("git", "action", 0),
            ],
        )

    def test_hard_dependency_overrides_profile_order(self):
        graph = build_graph(
            *inputs(module("consumer", requires=["base"]), module("base"))
        )
        self.assertLess(
            graph.order().index(NodeId("base", "finish")),
            graph.order().index(NodeId("consumer", "start")),
        )

    def test_empty_dependency_module_has_completion_barrier(self):
        graph = build_graph(
            *inputs(module("consumer", requires=["base"]), module("base", []))
        )
        self.assertIn(
            NodeId("base", "finish"), graph.ancestors(NodeId("consumer", "action", 0))
        )

    def test_missing_requires_fails_missing_after_warns(self):
        with self.assertRaisesRegex(GraphError, "requires target 'missing'"):
            build_graph(*inputs(module("consumer", requires=["missing"])))
        graph = build_graph(*inputs(module("consumer", after=["missing"])))
        self.assertEqual(len(graph.warnings), 1)
        self.assertIn("after target 'missing'", graph.warnings[0])

    def test_inactive_dependency_is_not_satisfied(self):
        repository, selections, plans = inputs(
            module("consumer", requires=["base"]), module("base")
        )
        selections["base"] = Selection(Result(Outcome.FALSE), (Result(Outcome.FALSE),))
        del plans[NodeId("base", "action", 0)]
        with self.assertRaisesRegex(GraphError, "inactive"):
            build_graph(repository, selections, plans)

    def test_conditioned_edges_only_activate_with_action(self):
        repository, selections, plans = inputs(
            module("consumer", [{"test": {}, "requires": ["missing"]}])
        )
        selections["consumer"] = Selection(
            Result(Outcome.TRUE), (Result(Outcome.FALSE),)
        )
        self.assertEqual(len(build_graph(repository, selections).order()), 2)
        selections["consumer"] = Selection(
            Result(Outcome.TRUE), (Result(Outcome.DEFERRED),)
        )
        self.assertIn(
            NodeId("consumer", "action", 0), build_graph(repository, selections).order()
        )
        selections["consumer"] = Selection(
            Result(Outcome.TRUE), (Result(Outcome.TRUE),)
        )
        with self.assertRaises(GraphError):
            build_graph(repository, selections, plans)

    def test_provider_dependencies_and_resources_are_retained(self):
        repository, selections, plans = inputs(module("consumer"), module("base"))
        key = NodeId("consumer", "action", 0)
        plans[key] = Plan(
            PlanStatus.CHANGE, "install", requires=("base",), resources=("network",)
        )
        graph = build_graph(repository, selections, plans)
        self.assertIn(NodeId("base", "finish"), graph.ancestors(key))
        self.assertEqual(graph.node(key).plan.resources, ("network",))

    def test_cycles_report_nodes_for_hard_and_soft_edges(self):
        for field in ("requires", "after"):
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(GraphError, "dependency cycle:.*one.*two"),
            ):
                build_graph(
                    *inputs(
                        module("one", **{field: ["two"]}),
                        module("two", requires=["one"]),
                    )
                )

    def test_self_dependency_is_a_cycle(self):
        with self.assertRaisesRegex(GraphError, "dependency cycle"):
            build_graph(*inputs(module("one", requires=["one"])))

    def test_bad_selection_and_extra_plans_fail(self):
        repository, selections, plans = inputs(module("one"))
        with self.assertRaisesRegex(GraphError, "exactly"):
            build_graph(repository, {})
        selections["one"] = Selection(Result(Outcome.TRUE), ())
        with self.assertRaisesRegex(GraphError, "action count"):
            build_graph(repository, selections)

    def test_long_cycles_do_not_exhaust_python_recursion(self):
        graph = ActionGraph()
        keys = [NodeId("long", "action", index) for index in range(1200)]
        for key in keys:
            graph.add(Node(key, Outcome.TRUE))
        for before, after in zip(keys, keys[1:]):
            graph.connect(before, after)
        self.assertEqual(graph.order(), tuple(keys))
        graph.connect(keys[-1], keys[0])
        with self.assertRaisesRegex(GraphError, "dependency cycle"):
            graph.order()
