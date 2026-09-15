"""Compose core action and fact providers without engine-specific dispatch."""

from etchlib import __version__
from etchlib.facts.core import core_registry as fact_registry
from etchlib.providers.commands.provider import CommandProvider
from etchlib.providers.filesystem.clean import CleanProvider
from etchlib.providers.filesystem.create import CreateProvider
from etchlib.providers.filesystem.link import LinkProvider
from etchlib.providers.installer.provider import InstallerProvider
from etchlib.providers.registry import Origin, Registry


def core_registry() -> Registry:
    registry = fact_registry()
    registry.register(
        Origin("Etch core", __version__, core=True),
        actions=[
            CreateProvider(),
            LinkProvider(),
            CleanProvider(),
            CommandProvider("shell"),
            CommandProvider("script"),
            InstallerProvider(),
        ],
    )
    return registry
