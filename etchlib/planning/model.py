"""One validated observation and dependency snapshot."""

from dataclasses import dataclass
from typing import Mapping, Optional

from etchlib.conditions.module import Selection
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import NodeId
from etchlib.ownership.claims import OwnedClaim
from etchlib.providers.observations import FactRef, FactResult, Inspection
from etchlib.providers.plans import Plan
from etchlib.providers.registry import Registration


@dataclass(frozen=True)
class Report:
    selections: Mapping[str, Selection]
    graph: ActionGraph
    plans: Mapping[NodeId, Plan]
    inspections: Mapping[NodeId, Inspection]
    providers: Mapping[NodeId, Registration]
    facts: Mapping[FactRef, Optional[FactResult]]
    claims: tuple[OwnedClaim, ...]
    registrations: tuple[Registration, ...]
