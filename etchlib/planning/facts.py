"""Lazy, detached observations for providers that request named facts."""

from collections.abc import Iterator, Mapping

from etchlib.facts.store import FactStore
from etchlib.providers.observations import FactRef, FactResult


class Observations(Mapping[FactRef, FactResult]):
    def __init__(self, store: FactStore) -> None:
        self.store = store
        self.requested: set[FactRef] = set()

    def __getitem__(self, key: FactRef) -> FactResult:
        if key not in self.store.references():
            raise KeyError(key)
        self.requested.add(key)
        return self.store.get(key)

    def __iter__(self) -> Iterator[FactRef]:
        return iter(self.store.references())

    def __len__(self) -> int:
        return len(self.store.references())
