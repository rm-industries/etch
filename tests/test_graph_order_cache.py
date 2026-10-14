"""A graph snapshot sorts once, and topology changes invalidate that result."""

from unittest import TestCase
from unittest.mock import patch

from etchlib.conditions.results import Outcome
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import GraphError, Node, NodeId
from etchlib.graph.topology import ordered


class GraphOrderCacheTests(TestCase):
    def test_order_is_reused_until_nodes_or_edges_change(self) -> None:
        graph = ActionGraph()
        a, b, c = (NodeId(name, "start") for name in ("a", "b", "c"))
        graph.add(Node(a, Outcome.TRUE))
        graph.add(Node(b, Outcome.TRUE))
        with patch("etchlib.graph.dag.ordered", wraps=ordered) as sort:
            self.assertEqual(graph.order(), (a, b))
            self.assertEqual(graph.order(), (a, b))
            self.assertEqual(sort.call_count, 1)
            graph.connect(b, a)
            self.assertEqual(graph.order(), (b, a))
            graph.add(Node(c, Outcome.TRUE))
            self.assertEqual(graph.order(), (b, a, c))
            self.assertEqual(sort.call_count, 3)
            graph.connect(a, b)
            with self.assertRaisesRegex(GraphError, "cycle"):
                graph.order()

    def test_empty_order_is_cached(self) -> None:
        graph = ActionGraph()
        with patch("etchlib.graph.dag.ordered", wraps=ordered) as sort:
            self.assertEqual(graph.order(), ())
            self.assertEqual(graph.order(), ())
            self.assertEqual(sort.call_count, 1)
