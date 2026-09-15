"""Lazy, scoped fact storage. Observation never implies action execution."""

from copy import deepcopy
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Dict

from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.observations import FactRef, FactResult, FactState
from etchlib.providers.registry import Registration, Registry


@dataclass(frozen=True)
class Declaration:
    provider: Registration
    config: Any
    context: Context


class FactStore:
    def __init__(self, registry: Registry):
        self.registry = registry
        self._declarations: Dict[FactRef, Declaration] = {}
        self._cache: Dict[FactRef, FactResult] = {}

    def declare(
        self, ref: FactRef, provider: str, config: Any, context: Context
    ) -> None:
        if ref in self._declarations:
            raise ProviderError("duplicate fact declaration {!r}".format(ref))
        entry = self.registry.fact(provider)
        self._declarations[ref] = Declaration(entry, deepcopy(config), context)

    def references(self):
        return tuple(self._declarations)

    def _require(self, ref):
        if ref not in self._declarations:
            raise ProviderError("undeclared fact {!r}".format(ref))

    def peek(self, ref):
        """Return a detached observation or None without triggering a probe."""
        self._require(ref)
        return deepcopy(self._cache.get(ref))

    def get(self, ref):
        self._require(ref)
        cached = self._cache.get(ref)
        if cached is None or cached.state is FactState.STALE:
            declaration = self._declarations[ref]
            observations = MappingProxyType(deepcopy(self._cache))
            context = replace(declaration.context, facts=observations)
            try:
                result = gather_fact(
                    declaration.provider, deepcopy(declaration.config), context
                )
                if result.state is FactState.STALE:
                    result = FactResult(
                        FactState.ERROR,
                        reason="provider returned STALE instead of a fresh observation",
                    )
            except ProviderError as exc:
                result = FactResult(FactState.ERROR, reason=str(exc))
            self._cache[ref] = deepcopy(result)
        return deepcopy(self._cache[ref])

    def invalidate(self, ref):
        """Mark only a previously observed fact stale; never gather immediately."""
        self._require(ref)
        cached = self._cache.get(ref)
        if cached is not None:
            self._cache[ref] = FactResult(
                FactState.STALE, cached.value, "explicitly invalidated"
            )
