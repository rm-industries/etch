"""Observation records shared by action and fact providers."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class InspectionState(Enum):
    SATISFIED = "satisfied"
    CHANGE = "change"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Inspection:
    state: InspectionState
    data: Any = None
    reason: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.state, InspectionState):
            raise ValueError("inspection state must be an InspectionState")


class FactState(Enum):
    VALUE = "value"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    ERROR = "error"


@dataclass(frozen=True)
class FactRef:
    module: str
    name: str

    def __post_init__(self):
        if not isinstance(self.module, str) or not self.module.strip():
            raise ValueError("fact reference requires a module")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("fact reference requires a local name")


@dataclass(frozen=True)
class FactResult:
    state: FactState
    value: Any = None
    reason: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.state, FactState):
            raise ValueError("fact state must be a FactState")
        if self.state in (FactState.UNAVAILABLE, FactState.ERROR):
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("unavailable/error facts require a reason")
            if self.value is not None:
                raise ValueError("unavailable/error facts cannot contain a value")
