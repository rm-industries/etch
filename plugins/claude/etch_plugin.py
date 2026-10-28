"""Explicit optional bundle; importing Etch core does not register Claude."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import ClaudeAction
from .facts import ClaudeFact

PLUGIN = {"name": "etch-claude", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (ClaudeAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(
        ClaudeFact(kind) for kind in ("command", "version", "marketplaces", "plugins")
    )
