"""Translate repository fact declarations into scoped storage."""

from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactRef

from .core import BUILTINS
from .store import FactStore


def repository_facts(repository, registry):
    store = FactStore(registry)
    global_context = Context(repository.root, repository.root, "", {})
    for name in BUILTINS:
        store.declare(FactRef(None, name), name, {}, global_context)
    for module in repository.modules:
        context = Context(repository.root, module.root, module.name, {})
        for name, declaration in module.config.get("facts", {}).items():
            provider, config = next(iter(declaration.items()))
            store.declare(FactRef(module.name, name), provider, config, context)
    return store
