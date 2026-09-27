"""Explicit Etch plugin entrypoint for macOS preference reconciliation."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import MacOSDefaultsAction

PLUGIN = {"name": "etch-macos-defaults", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (MacOSDefaultsAction(),)


def facts() -> tuple[FactProvider, ...]:
    return ()
