"""Normalize native inventories without confusing catalog entries with installs."""

from typing import Optional

from etchlib.providers.contracts import Context

from .cli import document
from .schema import Target, name, selector, source


def marketplaces(
    executable: str, target: Target, context: Context
) -> dict[str, Optional[str]]:
    rows = document(executable, target, ("plugin", "marketplace", "list"), context).get(
        "marketplaces"
    )
    if not isinstance(rows, list):
        raise ValueError("Codex marketplace inventory requires a marketplaces list")
    result: dict[str, Optional[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid Codex marketplace inventory row")
        key = name(row.get("name"))
        if key in result:
            raise ValueError("duplicate Codex marketplace name: " + key)
        origin = row.get("marketplaceSource")
        normalized = None
        if origin is not None:
            if (
                not isinstance(origin, dict)
                or not isinstance(origin.get("source"), str)
                or not isinstance(origin.get("sourceType"), str)
            ):
                raise ValueError("invalid Codex marketplace source metadata")
            if origin["sourceType"] in ("local", "git"):
                try:
                    normalized = source(origin["source"], context)
                except ValueError:
                    # Existing SSH/ref sources remain untouched; they cannot satisfy supported source declarations.
                    pass
        result[key] = normalized
    return result


def plugins(executable: str, target: Target, context: Context) -> tuple[str, ...]:
    data = document(executable, target, ("plugin", "list"), context)
    rows = data.get("installed")
    if not isinstance(rows, list):
        raise ValueError("Codex plugin inventory requires an installed list")
    installed = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("installed") is not True
            or type(row.get("enabled")) is not bool
        ):
            raise ValueError("invalid Codex installed plugin row")
        key = selector(row.get("pluginId"))
        if (
            key != name(row.get("name")) + "@" + name(row.get("marketplaceName"))
            or key in installed
        ):
            raise ValueError("inconsistent or duplicate Codex plugin identity")
        installed.add(key)
    return tuple(sorted(installed))
