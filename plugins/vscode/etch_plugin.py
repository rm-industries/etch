"""Explicit source-plugin entrypoint; importing Etch core does not load this bundle."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import VSCodeAction
from .facts import VSCodeFact

PLUGIN = {"name": "etch-vscode", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (VSCodeAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(VSCodeFact(kind) for kind in ("command", "version", "extensions"))
