"""Reconcile only declared preference keys; leave the rest of a domain intact."""

import platform
from dataclasses import dataclass
from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import read_domain, write_key
from .schema import Preferences, Value, preferences


def _different(current: dict[str, Any], key: str, desired: Value) -> bool:
    return (
        key not in current
        or type(current[key]) is not type(desired)
        or current[key] != desired
    )


def _macos() -> None:
    if platform.system() != "Darwin":
        raise ValueError(
            "macos_defaults is available only on macOS; guard the module with when: {'os': 'macos'}"
        )


@dataclass(frozen=True)
class Reconciliation:
    preferences: Preferences
    drift: tuple[tuple[str, str], ...]


class MacOSDefaultsAction:
    name = "macos_defaults"

    def validate(self, config: Any, context: Context) -> None:
        preferences(config)

    def inspect(self, config: Any, context: Context) -> Inspection:
        desired = preferences(config)
        _macos()
        current = read_domain(desired.domain)
        drift = tuple(
            (key, "missing" if key not in current else "different")
            for key, value in desired.values.items()
            if _different(current, key, value)
        )
        return Inspection(
            InspectionState.CHANGE if drift else InspectionState.SATISFIED,
            Reconciliation(desired, drift),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Reconciliation = observation.data
        details = ", ".join(
            "{} ({})".format(key, reason) for key, reason in state.drift
        )
        return Plan(
            PlanStatus.CHANGE if state.drift else PlanStatus.SKIP,
            "macOS preferences {}: {}".format(
                state.preferences.domain,
                details if details else "declared keys already match",
            ),
            payload=state.preferences,
            resources=("preferences:" + state.preferences.domain.lower(),),
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        desired: Preferences = plan.payload
        _macos()
        current = read_domain(desired.domain)
        changed = []
        for key, value in desired.values.items():
            if _different(current, key, value):
                write_key(desired.domain, key, value)
                changed.append(key)
        return ApplyResult(
            bool(changed),
            "macOS preferences {}: {}".format(
                desired.domain,
                "updated " + ", ".join(changed) if changed else "already match",
            ),
        )
