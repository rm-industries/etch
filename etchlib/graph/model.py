"""Graph identities and execution-node metadata."""

from dataclasses import dataclass
from typing import Optional

from etchlib.conditions.results import Outcome
from etchlib.providers.observations import FactRef
from etchlib.providers.plans import Plan


class GraphError(ValueError):
    """Invalid graph topology, dependency or refresh relationship."""


@dataclass(frozen=True)
class NodeId:
    module: str
    kind: str
    index: int = -1
    fact: Optional[FactRef] = None

    def __str__(self):
        label = "{}:{}".format(self.module, self.kind)
        if self.index >= 0:
            label += "[{}]".format(self.index)
        if self.fact is not None:
            label += "({}.{})".format(self.fact.module or "global", self.fact.name)
        return label


@dataclass(frozen=True)
class Node:
    id: NodeId
    outcome: Outcome
    plan: Optional[Plan] = None


@dataclass(frozen=True)
class FactLink:
    producer: NodeId
    consumer: NodeId
    fact: FactRef
