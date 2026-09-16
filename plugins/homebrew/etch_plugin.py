"""Explicit source-bundle entrypoint with independent release/API metadata."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import BrewAction
from .facts import BrewFact

PLUGIN = {"name": "etch-homebrew", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (BrewAction(),)


def facts() -> tuple[FactProvider, ...]:
    return tuple(BrewFact(kind) for kind in ("command", "version", "formulae", "casks"))
