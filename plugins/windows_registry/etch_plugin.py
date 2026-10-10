"""Explicit Etch entrypoint for current-user Registry preferences."""

from etchlib.providers.contracts import ActionProvider, FactProvider

from .action import WindowsRegistryAction

PLUGIN = {"name": "etch-windows-registry", "version": "0.1.0", "api": 1}


def actions() -> tuple[ActionProvider, ...]:
    return (WindowsRegistryAction(),)


def facts() -> tuple[FactProvider, ...]:
    return ()
