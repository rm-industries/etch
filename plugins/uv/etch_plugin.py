"""Explicit source-bundle entrypoint; not registered by the core engine."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import UvAction
from .facts import UvFact

PLUGIN = {"name": "etch-uv", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (UvAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(UvFact(kind) for kind in ("command", "version", "tools"))
