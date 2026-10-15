"""Explicit optional bundle; importing Etch core does not register Codex."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import CodexAction
from .facts import CodexFact

PLUGIN = {"name": "etch-codex", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (CodexAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(
        CodexFact(kind) for kind in ("command", "version", "marketplaces", "plugins")
    )
