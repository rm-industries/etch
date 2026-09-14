"""Register core observations through the same registry used by plugins."""
from etchlib import __version__
from etchlib.providers.registry import Origin, Registry
from .platform import PlatformProbe
from .probes import LocalProbe

BUILTINS = ("os", "distro", "arch")


def core_registry():
    registry = Registry()
    providers = [PlatformProbe(name) for name in BUILTINS]
    providers.extend(LocalProbe(name) for name in (
        "command", "command_path", "env", "path_exists", "file_exists", "directory_exists"))
    registry.register(Origin("Etch core", __version__, core=True), facts=providers)
    return registry
