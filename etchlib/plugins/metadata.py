"""Validate bundle metadata independently from provider registration."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etchlib import PLUGIN_API_VERSION


class PluginError(ValueError):
    """An invalid plugin declaration or failed load."""


@dataclass(frozen=True)
class Metadata:
    name: str
    version: str
    api: int
    root: Path


def parse_metadata(value: Any, root: Path) -> Metadata:
    if not isinstance(value, dict) or set(value) != {"name", "version", "api"}:
        raise PluginError("{}: PLUGIN must contain name, version and api".format(root))
    for field in ("name", "version"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise PluginError("{}: PLUGIN.{} must be a nonempty string".format(root, field))
    if type(value["api"]) is not int or value["api"] != PLUGIN_API_VERSION:
        raise PluginError("{}: incompatible plugin API {!r}; Etch supports {}".format(
            root, value["api"], PLUGIN_API_VERSION))
    return Metadata(value["name"], value["version"], value["api"], root)
