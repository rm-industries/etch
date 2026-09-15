"""Dependency storage and validated evidence for condition reevaluation."""

from typing import cast

from etchlib.conditions.results import Outcome
from etchlib.providers.observations import FactRef
from etchlib.providers.plans import PlanStatus

from .model import GraphError, Node, NodeId
from .topology import ordered


class ActionGraph:
    def __init__(self) -> None:
        self._nodes: dict[NodeId, Node] = {}
        self._parents: dict[NodeId, dict[NodeId, None]] = {}
        self._children: dict[NodeId, dict[NodeId, None]] = {}
        self.warnings: list[str] = []

    def add(self, node: Node) -> None:
        if node.id in self._nodes:
            raise GraphError("duplicate graph node {}".format(node.id))
        self._nodes[node.id] = node
        self._parents[node.id] = {}
        self._children[node.id] = {}

    def node(self, key: NodeId) -> Node:
        if key not in self._nodes:
            raise GraphError("missing graph node {}".format(key))
        return self._nodes[key]

    def connect(self, before: NodeId, after: NodeId) -> None:
        self.node(before)
        self.node(after)
        self._parents[after][before] = None
        self._children[before][after] = None

    def order(self) -> tuple[NodeId, ...]:
        return ordered(self._nodes, self._parents, self._children)

    def ancestors(self, key: NodeId) -> set[NodeId]:
        self.node(key)
        seen, pending = set(), list(self._parents[key])
        while pending:
            parent = pending.pop()
            if parent not in seen:
                seen.add(parent)
                pending.extend(self._parents[parent])
        return seen

    def earlier_refresh(self, consumer: NodeId) -> dict[FactRef, str]:
        """Only preceding, fully enabled producers justify deferred conditions."""
        order = self.order()  # Refuse evidence from a cyclic graph.
        ancestors = self.ancestors(consumer)
        evidence = {}
        for key in order:
            if key.kind != "refresh" or key not in ancestors:
                continue
            producer = NodeId(key.module, "action", key.index)
            node = self.node(producer)
            if (
                node.outcome is not Outcome.TRUE
                or node.plan is None
                or node.plan.status is PlanStatus.SKIP
            ):
                continue
            if any(
                self.node(parent).outcome is not Outcome.TRUE
                for parent in self.ancestors(key)
            ):
                continue
            # build_graph supplies a FactRef for every refresh node.
            evidence[cast(FactRef, key.fact)] = str(producer)
        return evidence
