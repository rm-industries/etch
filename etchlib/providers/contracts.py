"""Structural protocols: provider implementations need no shared base class."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from .observations import FactRef, FactResult, Inspection
from .plans import ApplyResult, Plan


@dataclass(frozen=True)
class Context:
    repo_root: Path
    module_root: Path
    module_name: str
    facts: Mapping[FactRef, FactResult]
    defaults: Mapping[str, Any] = field(default_factory=dict)
    elevation_allowed: bool = False


class ActionProvider(Protocol):
    name: str

    def validate(self, config: Any, context: Context) -> None:
        """Reject unsupported configuration before inspecting or applying."""
        ...

    def inspect(self, config: Any, context: Context) -> Inspection: ...

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan: ...

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        """Run only after the engine validates dependencies, claims and privilege."""
        ...


class FactProvider(Protocol):
    name: str

    def validate(self, config: Any, context: Context) -> None: ...

    def gather(self, config: Any, context: Context) -> FactResult: ...
