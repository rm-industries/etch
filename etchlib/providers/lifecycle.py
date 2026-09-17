"""Checked observation and planning calls; this is not an executor."""

from typing import Any

from .contracts import Context
from .errors import ProviderError
from .observations import FactResult, Inspection
from .plans import ApplyResult, Plan
from .registry import Registration


def _call(entry: Registration, method: str, *args: Any) -> Any:
    try:
        return getattr(entry.provider, method)(*args)
    except Exception as exc:
        raise ProviderError(
            "{} provider {!r} from {}: {} failed: {}".format(
                entry.kind, entry.name, entry.origin.name, method, exc
            )
        ) from exc


def _validate(entry: Registration, kind: str, config: Any, context: Context) -> None:
    if entry.kind != kind:
        raise ProviderError("expected {} provider, got {}".format(kind, entry.kind))
    if _call(entry, "validate", config, context) is not None:
        raise ProviderError(
            "provider {!r}: validate must return None or raise".format(entry.name)
        )


def validate_action(entry: Registration, config: Any, context: Context) -> None:
    """Check an action schema without inspecting or applying it."""
    _validate(entry, "action", config, context)


def plan_action(entry: Registration, config: Any, context: Context) -> Plan:
    return inspect_action(entry, config, context)[1]


def inspect_action(
    entry: Registration, config: Any, context: Context
) -> tuple[Inspection, Plan]:
    """Return the current observation and its checked, non-applied plan."""
    _validate(entry, "action", config, context)
    observation = _call(entry, "inspect", config, context)
    if not isinstance(observation, Inspection):
        raise ProviderError(
            "provider {!r}: inspect must return Inspection".format(entry.name)
        )
    plan = _call(entry, "plan", config, observation, context)
    if not isinstance(plan, Plan):
        raise ProviderError("provider {!r}: plan must return Plan".format(entry.name))
    return observation, plan


def gather_fact(entry: Registration, config: Any, context: Context) -> FactResult:
    _validate(entry, "fact", config, context)
    fact = _call(entry, "gather", config, context)
    if not isinstance(fact, FactResult):
        raise ProviderError(
            "provider {!r}: gather must return FactResult".format(entry.name)
        )
    return fact


def apply_action(entry: Registration, plan: Plan, context: Context) -> ApplyResult:
    """Normalize failures/results at the mutation boundary."""
    if entry.kind != "action":
        raise ProviderError("apply requires an action provider")
    if plan.elevated and not context.elevation_allowed:
        raise ProviderError("privilege escalation has not been authorized")
    result = _call(entry, "apply", plan, context)
    if not isinstance(result, ApplyResult):
        raise ProviderError(
            "provider {!r}: apply must return ApplyResult".format(entry.name)
        )
    return result
