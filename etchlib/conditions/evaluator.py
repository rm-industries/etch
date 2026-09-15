"""Evaluate scoped conditions; scheduling evidence is supplied by the planner."""

from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Optional, Tuple

from etchlib.facts.store import FactStore
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.observations import FactRef, FactState
from etchlib.versions.constraints import matches

from .results import ConditionError, Outcome, Result
from .schema import validate


@dataclass(frozen=True)
class _Pending:
    result: Result
    unresolved: Tuple[str, ...] = ()


def _combine(parts: Iterable[_Pending], conjunction: bool) -> _Pending:
    decisive = Outcome.FALSE if conjunction else Outcome.TRUE
    waiting: list[FactRef] = []
    reasons: list[str] = []
    unresolved: list[str] = []
    for part in parts:
        if part.result.outcome is decisive:
            return _Pending(Result(decisive))
        waiting.extend(part.result.waiting)
        reasons.extend(part.result.reasons)
        unresolved.extend(part.unresolved)
    if waiting or unresolved:
        return _Pending(
            Result(Outcome.DEFERRED, tuple(dict.fromkeys(waiting)), tuple(reasons)),
            tuple(unresolved),
        )
    return _Pending(Result(Outcome.TRUE if conjunction else Outcome.FALSE))


class Evaluator:
    def __init__(
        self,
        store: FactStore,
        context: Context,
        earlier_refresh: Optional[Mapping[FactRef, str]] = None,
    ) -> None:
        self.store = store
        self.context = context
        # Entries identify an earlier eligible producer, not merely a refresh declaration.
        self.earlier_refresh = dict(earlier_refresh or {})
        if any(
            not isinstance(ref, FactRef)
            or not isinstance(producer, str)
            or not producer.strip()
            for ref, producer in self.earlier_refresh.items()
        ):
            raise ConditionError(
                "earlier refresh evidence must map fact references to producer identifiers"
            )

    def evaluate(self, condition: Any) -> Result:
        validate(condition)
        try:
            pending = self._dictionary(condition)
        except ProviderError as exc:
            raise ConditionError(str(exc)) from exc
        if pending.unresolved:
            raise ConditionError(
                "Unresolved condition: " + "; ".join(pending.unresolved)
            )
        return pending.result

    def _dictionary(self, condition: Mapping[str, Any]) -> _Pending:
        def clauses() -> Iterator[_Pending]:
            for key, value in condition.items():
                if key == "not":
                    child = self._dictionary(value)
                    inverted = {
                        Outcome.TRUE: Outcome.FALSE,
                        Outcome.FALSE: Outcome.TRUE,
                        Outcome.DEFERRED: Outcome.DEFERRED,
                    }[child.result.outcome]
                    yield _Pending(
                        Result(inverted, child.result.waiting, child.result.reasons),
                        child.unresolved,
                    )
                else:
                    values = value if isinstance(value, list) else [value]
                    yield _combine((self._leaf(key, item) for item in values), False)

        return _combine(clauses(), True)

    def _leaf(self, key: str, value: Any) -> _Pending:
        if key == "fact":
            ref = FactRef(self.context.module_name, value["name"])
            cached = self.store.peek(ref)
            if (
                cached is not None
                and cached.state is FactState.STALE
                and ref in self.earlier_refresh
            ):
                return self._missing(ref, "observation is stale")
            observation = self.store.get(ref)
            if observation.state is FactState.ERROR:
                raise ConditionError("fact {!r}: {}".format(ref, observation.reason))
            if observation.state is not FactState.VALUE:
                return self._missing(
                    ref, observation.reason or "observation unavailable"
                )
            if "matches" in value:
                try:
                    accepted = matches(observation.value, value["matches"])
                except (ValueError, TypeError) as exc:
                    raise ConditionError("fact {!r}: {}".format(ref, exc)) from exc
            elif "equals" in value:
                accepted = (
                    type(observation.value) is type(value["equals"])
                    and observation.value == value["equals"]
                )
            else:
                if type(observation.value) is not bool:
                    raise ConditionError(
                        "fact {!r}: bare fact conditions require a boolean value".format(
                            ref
                        )
                    )
                accepted = observation.value
        else:
            if key in ("os", "distro", "arch"):
                observation = self.store.get(FactRef(None, key))
                expected = value
            else:
                query = value["name"] if isinstance(value, dict) else value
                observation = gather_fact(
                    self.store.registry.fact(key), query, self.context
                )
                expected = value.get("equals") if isinstance(value, dict) else None
            if observation.state is FactState.ERROR:
                raise ConditionError("{} condition: {}".format(key, observation.reason))
            if observation.state is not FactState.VALUE:
                accepted = False
            elif key == "command" or (key == "env" and expected is None):
                accepted = True
            else:
                accepted = observation.value == expected
        return _Pending(Result(Outcome.TRUE if accepted else Outcome.FALSE))

    def _missing(self, ref: FactRef, reason: str) -> _Pending:
        producer = self.earlier_refresh.get(ref)
        if producer is not None:
            return _Pending(
                Result(
                    Outcome.DEFERRED,
                    (ref,),
                    ("{}; waiting for {}".format(reason, producer),),
                )
            )
        problem = "{} in module {}: {}; no earlier producer/refresh path".format(
            ref.name, ref.module, reason
        )
        return _Pending(Result(Outcome.DEFERRED), (problem,))
