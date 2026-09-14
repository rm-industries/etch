"""Dependency storage and validated evidence for condition reevaluation."""
from etchlib.conditions.results import Outcome
from etchlib.providers.plans import PlanStatus
from .model import GraphError, NodeId
from .topology import ordered


class ActionGraph:
    def __init__(self):
        self._nodes = {}
        self._parents = {}
        self._children = {}
        self.warnings = []

    def add(self, node):
        if node.id in self._nodes:
            raise GraphError("duplicate graph node {}".format(node.id))
        self._nodes[node.id] = node
        self._parents[node.id] = {}
        self._children[node.id] = {}

    def node(self, key):
        if key not in self._nodes:
            raise GraphError("missing graph node {}".format(key))
        return self._nodes[key]

    def connect(self, before, after):
        self.node(before)
        self.node(after)
        self._parents[after][before] = None
        self._children[before][after] = None

    def order(self):
        return ordered(self._nodes, self._parents, self._children)

    def ancestors(self, key):
        self.node(key)
        seen, pending = set(), list(self._parents[key])
        while pending:
            parent = pending.pop()
            if parent not in seen:
                seen.add(parent)
                pending.extend(self._parents[parent])
        return seen

    def earlier_refresh(self, consumer):
        """Only preceding, fully enabled producers justify deferred conditions."""
        order = self.order()  # Refuse evidence from a cyclic graph.
        ancestors = self.ancestors(consumer)
        evidence = {}
        for key in order:
            if key.kind != "refresh" or key not in ancestors:
                continue
            producer = NodeId(key.module, "action", key.index)
            node = self.node(producer)
            if node.outcome is not Outcome.TRUE or node.plan is None or node.plan.status is PlanStatus.SKIP:
                continue
            if any(self.node(parent).outcome is not Outcome.TRUE for parent in self.ancestors(key)):
                continue
            evidence[key.fact] = str(producer)
        return evidence
