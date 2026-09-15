"""Checked observation and planning calls; this is not an executor."""

from typing import Any

from .contracts import Context
from .errors import ProviderError
from .observations import FactResult, Inspection
from .plans import Plan
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


def plan_action(entry: Registration, config: Any, context: Context) -> Plan:
    _validate(entry, "action", config, context)
    observation = _call(entry, "inspect", config, context)
    if not isinstance(observation, Inspection):
        raise ProviderError(
            "provider {!r}: inspect must return Inspection".format(entry.name)
        )
    plan = _call(entry, "plan", config, observation, context)
    if not isinstance(plan, Plan):
        raise ProviderError("provider {!r}: plan must return Plan".format(entry.name))
    return plan


def gather_fact(entry: Registration, config: Any, context: Context) -> FactResult:
    _validate(entry, "fact", config, context)
    fact = _call(entry, "gather", config, context)
    if not isinstance(fact, FactResult):
        raise ProviderError(
            "provider {!r}: gather must return FactResult".format(entry.name)
        )
    return fact
