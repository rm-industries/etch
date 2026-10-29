"""Explicit source-bundle entrypoint with independent release/API metadata."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import WingetAction
from .facts import WingetFact

PLUGIN = {"name": "etch-winget", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (WingetAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(WingetFact(kind) for kind in ("command", "version", "packages"))
