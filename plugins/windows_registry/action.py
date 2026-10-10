"""Inspect and reconcile only declared current-user Registry values."""

from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .access import read, registry, write
from .schema import Preferences, preferences


def different(
    desired: Preferences, current: dict[str, tuple[Any, int]]
) -> tuple[str, ...]:
    api = registry()
    return tuple(
        name
        for name, value in desired.values.items()
        if current.get(name) != (value["data"], getattr(api, value["type"]))
    )


class WindowsRegistryAction:
    name = "windows_registry"

    def validate(self, config: Any, context: Context) -> None:
        preferences(config)

    def inspect(self, config: Any, context: Context) -> Inspection:
        desired = preferences(config)
        current = read(desired)
        drift = different(desired, current)
        return Inspection(
            InspectionState.CHANGE if drift else InspectionState.SATISFIED,
            (desired, current, drift),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        desired, current, drift = observation.data
        details = []
        api = registry()
        types = {
            getattr(api, name): name
            for name in (
                "REG_SZ",
                "REG_EXPAND_SZ",
                "REG_DWORD",
                "REG_QWORD",
                "REG_MULTI_SZ",
            )
        }
        for name in drift:
            value = desired.values[name]
            before = "missing key/value"
            if name in current:
                data, kind = current[name]
                before = "{} {!r}".format(
                    types.get(kind, "Registry type {}".format(kind)), data
                )
            details.append(
                "{}: {} -> {} {!r}".format(name, before, value["type"], value["data"])
            )
        return Plan(
            PlanStatus.CHANGE if drift else PlanStatus.SKIP,
            "Registry HKEY_CURRENT_USER\\{}: {}".format(
                desired.key,
                "; ".join(details) if details else "declared values already match",
            ),
            payload=desired,
            resources=("registry:hkcu:64:" + desired.key.casefold(),),
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        desired: Preferences = plan.payload
        drift = different(desired, read(desired))
        if drift:
            write(desired, drift)
        return ApplyResult(
            bool(drift),
            "Registry {}: {}".format(
                desired.key, "updated " + ", ".join(drift) if drift else "already match"
            ),
        )
