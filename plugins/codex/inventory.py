"""Normalize native inventories without confusing catalog entries with installs."""

import os
from typing import Optional, cast

from etchlib.providers.contracts import Context

from .cli import document
from .schema import Target, name, selector, source


def _cache_key(
    kind: str, executable: str, target: Target, context: Context
) -> tuple[str, ...]:
    # Native inventories can depend on project configuration as well as user home.
    return (
        "codex.inventory",
        kind,
        executable,
        str(target.timeout),
        str(context.module_root),
        os.environ.get("CODEX_HOME", ""),
        os.environ.get("HOME", ""),
        os.environ.get("USERPROFILE", ""),
    )


def marketplaces(
    executable: str, target: Target, context: Context
) -> dict[str, Optional[str]]:
    key = _cache_key("marketplaces", executable, target, context)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return dict(cast(dict[str, Optional[str]], cache[key]))
    rows = document(executable, target, ("plugin", "marketplace", "list"), context).get(
        "marketplaces"
    )
    if not isinstance(rows, list):
        raise ValueError("Codex marketplace inventory requires a marketplaces list")
    result: dict[str, Optional[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid Codex marketplace inventory row")
        market = name(row.get("name"))
        if market in result:
            raise ValueError("duplicate Codex marketplace name: " + market)
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
        result[market] = normalized
    if cache is not None:
        cache[key] = dict(result)
    return result


def plugins(executable: str, target: Target, context: Context) -> tuple[str, ...]:
    key = _cache_key("plugins", executable, target, context)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(tuple[str, ...], cache[key])
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
        plugin = selector(row.get("pluginId"))
        if (
            plugin != name(row.get("name")) + "@" + name(row.get("marketplaceName"))
            or plugin in installed
        ):
            raise ValueError("inconsistent or duplicate Codex plugin identity")
        installed.add(plugin)
    result = tuple(sorted(installed))
    if cache is not None:
        cache[key] = result
    return result
