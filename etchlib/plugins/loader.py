"""Build a registry from declared source paths without mutating the input registry."""
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from etchlib.providers.registry import Origin, Registry
from .metadata import Metadata, PluginError, parse_metadata
from .source import discard, load_source


@dataclass(frozen=True)
class LoadedPlugins:
    registry: Registry
    plugins: Tuple[Metadata, ...]


def load_plugins(repo_root: Path, paths: Iterable[str], core: Registry) -> LoadedPlugins:
    if isinstance(paths, (str, bytes)):
        raise PluginError("plugin declarations must be a collection of paths")
    roots = []
    for value in paths:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise PluginError("plugin declarations must be nonempty paths")
        try:
            root = (repo_root / value).resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise PluginError("invalid plugin path {!r}: {}".format(value, exc)) from exc
        if root in roots:
            raise PluginError("{}: duplicate plugin path".format(root))
        if not (root / "etch_plugin.py").is_file():
            raise PluginError("{}: missing plugin entrypoint etch_plugin.py".format(root))
        roots.append(root)
    registry = core.copy()
    modules, metadata, names = [], [], set()
    try:
        for root in roots:
            module = load_source(root)
            modules.append(module)
            info = parse_metadata(getattr(module, "PLUGIN", None), root)
            if info.name in names:
                raise PluginError("{}: duplicate plugin name {!r}".format(root, info.name))
            names.add(info.name)
            bundles = []
            for kind in ("actions", "facts"):
                factory = getattr(module, kind, None)
                if not callable(factory):
                    raise PluginError("{}: {} must be a callable factory".format(root, kind))
                bundles.append(tuple(factory()))
            registry.register(Origin(info.name, info.version), actions=bundles[0], facts=bundles[1])
            metadata.append(info)
    except (Exception, SystemExit) as exc:
        for module in modules:
            discard(module)
        if isinstance(exc, PluginError):
            raise
        raise PluginError("{}: plugin loading failed: {}".format(root, exc)) from exc
    return LoadedPlugins(registry, tuple(metadata))
