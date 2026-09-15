"""Normalized plans; interpretation and scheduling belong to the engine."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Tuple

from .observations import FactRef


class PlanStatus(Enum):
    SKIP = "skip"
    CHANGE = "change"
    RUN = "run"


class ClaimKind(Enum):
    EXCLUSIVE = "exclusive"
    SHARED_DIRECTORY = "shared-directory"


@dataclass(frozen=True)
class PathClaim:
    path: Path
    kind: ClaimKind = ClaimKind.EXCLUSIVE

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise ValueError("path claims require an absolute Path")
        if not isinstance(self.kind, ClaimKind):
            raise ValueError("claim kind must be a ClaimKind")


@dataclass(frozen=True)
class Plan:
    status: PlanStatus
    description: str
    payload: Any = None
    requires: Tuple[str, ...] = ()
    after: Tuple[str, ...] = ()
    facts: Tuple[FactRef, ...] = ()
    claims: Tuple[PathClaim, ...] = ()
    refresh: Tuple[FactRef, ...] = ()
    resources: Tuple[str, ...] = ()
    elevated: bool = False
    network: bool = False
    opaque: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, PlanStatus):
            raise ValueError("plan status must be a PlanStatus")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("plan requires a description")
        for field, item_type in (
            ("requires", str),
            ("after", str),
            ("facts", FactRef),
            ("claims", PathClaim),
            ("refresh", FactRef),
            ("resources", str),
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not isinstance(v, item_type) for v in values
            ):
                raise ValueError(
                    "{} must be a tuple of {}".format(field, item_type.__name__)
                )
            if item_type is str and any(not v.strip() for v in values):
                raise ValueError("{} cannot contain empty names".format(field))
        for field in ("elevated", "network", "opaque"):
            if type(getattr(self, field)) is not bool:
                raise ValueError("{} must be a boolean".format(field))


@dataclass(frozen=True)
class ApplyResult:
    changed: bool
    description: str

    def __post_init__(self) -> None:
        if type(self.changed) is not bool or not isinstance(self.description, str):
            raise ValueError(
                "apply result requires a boolean changed flag and string description"
            )
