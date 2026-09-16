"""Normalized action outcomes and a complete, ordered run report."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from etchlib.graph.model import NodeId
from etchlib.providers.observations import FactRef, FactResult


class Status(Enum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ActionResult:
    node: NodeId
    status: Status
    description: str
    refreshed: tuple[FactRef, ...] = ()


@dataclass(frozen=True)
class ExecutionReport:
    actions: tuple[ActionResult, ...]
    facts: Mapping[FactRef, Optional[FactResult]]
    warnings: tuple[str, ...] = ()
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and all(
            result.status not in (Status.FAILED, Status.BLOCKED)
            for result in self.actions
        )
