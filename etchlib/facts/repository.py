"""Translate repository fact declarations into scoped storage."""

from typing import Any

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.results import ConditionError, Outcome
from etchlib.conditions.schema import validate
from etchlib.config import Repository, fact_provider
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import FactRef
from etchlib.providers.registry import Registry

from .core import BUILTINS
from .store import FactStore


def _uses_fact(condition: dict[str, Any]) -> bool:
    return "fact" in condition or ("not" in condition and _uses_fact(condition["not"]))


def _select(declaration: Any, store: FactStore, context: Context) -> tuple[str, Any]:
    if isinstance(declaration, list):
        for alternative in declaration:
            gate = alternative["when"]
            validate(gate)
            if _uses_fact(gate):
                raise ProviderError(
                    "fact alternative conditions cannot reference facts"
                )
        matches = []
        for index, alternative in enumerate(declaration):
            gate = alternative["when"]
            if Evaluator(store, context).evaluate(gate).outcome is Outcome.TRUE:
                matches.append(index)
        if len(matches) != 1:
            raise ProviderError(
                "expected one matching fact alternative, found {}".format(len(matches))
            )
        declaration = declaration[matches[0]]
    return fact_provider(declaration)


def repository_facts(repository: Repository, registry: Registry) -> FactStore:
    store = FactStore(registry)
    global_context = Context(repository.root, repository.root, "", {})
    for name in BUILTINS:
        store.declare(FactRef(None, name), name, {}, global_context)
    for module in repository.modules:
        context = Context(repository.root, module.root, module.name, {})
        for name, declaration in module.config.get("facts", {}).items():
            try:
                provider, config = _select(declaration, store, context)
                store.declare(FactRef(module.name, name), provider, config, context)
            except (ProviderError, ConditionError) as exc:
                raise ProviderError(
                    "module {!r} fact {!r}: {}".format(module.name, name, exc)
                ) from exc
    return store
