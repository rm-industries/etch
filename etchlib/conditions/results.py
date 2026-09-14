"""Public outcomes and diagnostics for condition consumers."""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from etchlib.providers.observations import FactRef


class Outcome(Enum):
    TRUE = "true"
    FALSE = "false"
    DEFERRED = "deferred"


class ConditionError(ValueError):
    """Malformed condition, failed observation, or unresolved required fact."""


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    waiting: Tuple[FactRef, ...] = ()
    reasons: Tuple[str, ...] = ()

    def __bool__(self):
        raise TypeError("inspect Result.outcome explicitly; DEFERRED is not a boolean")
