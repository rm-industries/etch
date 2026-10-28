"""Explicit source-bundle entrypoint; not registered by the core engine."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import NpmAction
from .facts import NpmFact

PLUGIN = {"name": "etch-npm", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (NpmAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(NpmFact(kind) for kind in ("command", "version", "packages"))
