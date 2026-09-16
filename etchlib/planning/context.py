"""Fresh provider contexts with lazy detached facts and copied defaults."""

from copy import deepcopy
from types import MappingProxyType

from etchlib.config import Module, Repository
from etchlib.facts.store import FactStore
from etchlib.providers.contracts import Context

from .facts import Observations


def provider_context(
    repository: Repository,
    module: Module,
    store: FactStore,
    elevation_allowed: bool = False,
) -> Context:
    return Context(
        repository.root,
        module.root,
        module.name,
        Observations(store),
        MappingProxyType(deepcopy(repository.defaults.get("defaults", {}))),
        elevation_allowed,
    )
