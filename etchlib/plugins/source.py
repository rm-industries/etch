"""Load an explicitly selected entrypoint with isolated relative imports."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from .metadata import PluginError


def discard(module: ModuleType) -> None:
    prefix = module.__name__
    for name in tuple(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            del sys.modules[name]


def load_source(root: Path) -> ModuleType:
    entry = root / "etch_plugin.py"
    if not root.is_dir() or not entry.is_file():
        raise PluginError("{}: missing plugin entrypoint etch_plugin.py".format(root))
    # Every load gets a private package namespace, including its relative imports.
    name = "_etch_plugin_" + uuid4().hex
    spec = importlib.util.spec_from_file_location(
        name, entry, submodule_search_locations=[str(root)]
    )
    if spec is None or spec.loader is None:
        raise PluginError("{}: cannot create plugin module".format(entry))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        # Read the entrypoint directly so a same-size edit cannot reuse stale bytecode.
        exec(compile(entry.read_bytes(), str(entry), "exec"), module.__dict__)
    except (Exception, SystemExit) as exc:
        discard(module)
        raise PluginError("{}: plugin import failed: {}".format(entry, exc)) from exc
    return module
