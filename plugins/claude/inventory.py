"""Validate Claude's native JSON arrays and count only user plugin installs."""

import os
from typing import Optional, cast

from etchlib.providers.contracts import Context

from .cli import document
from .schema import Target, name, selector, source


def _cache_key(
    kind: str, executable: str, target: Target, context: Context
) -> tuple[str, ...]:
    return (
        "claude.inventory",
        kind,
        executable,
        str(target.timeout),
        str(context.module_root),
        *(
            os.environ.get(key, "")
            for key in (
                "CLAUDE_CONFIG_DIR",
                "CLAUDE_CODE_PLUGIN_CACHE_DIR",
                "HOME",
                "USERPROFILE",
                "XDG_CONFIG_HOME",
                "APPDATA",
                "LOCALAPPDATA",
            )
        ),
    )


def marketplaces(
    executable: str, target: Target, context: Context
) -> dict[str, Optional[str]]:
    key = _cache_key("marketplaces", executable, target, context)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return dict(cast(dict[str, Optional[str]], cache[key]))
    rows = document(executable, target, ("plugin", "marketplace", "list"), context)
    result: dict[str, Optional[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid Claude marketplace inventory row")
        market = name(row.get("name"))
        if market in result:
            raise ValueError("duplicate Claude marketplace name: " + market)
        kind = row.get("source")
        if kind not in ("github", "git", "url", "directory", "file", "claudeai"):
            raise ValueError("unsupported Claude marketplace source type")
        field = {
            "github": "repo",
            "git": "url",
            "url": "url",
            "directory": "path",
            "file": "path",
        }.get(kind)
        origin = row.get(field) if field else None
        if field and (not isinstance(origin, str) or not origin.strip()):
            raise ValueError("invalid Claude marketplace source metadata")
        normalized = None
        if kind in ("github", "git", "directory", "file") and not row.get("ref"):
            try:
                normalized = source(origin, context)
            except ValueError:
                # Preserve unsupported existing SSH/ref sources without treating them as requested sources.
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
    rows = document(executable, target, ("plugin", "list"), context)
    result = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not isinstance(row.get("version"), str)
            or not row["version"]
            or type(row.get("enabled")) is not bool
            or not isinstance(row.get("installPath"), str)
            or row.get("scope")
            not in ("user", "project", "local", "managed", "session", "synced")
        ):
            raise ValueError("invalid Claude installed plugin row")
        if row["scope"] != "user" or row["id"].endswith(
            ("@inline", "@skills-dir", "@synced")
        ):
            continue
        plugin = selector(row["id"])
        if plugin in result:
            raise ValueError("duplicate Claude user plugin identity: " + plugin)
        result.add(plugin)
    values = tuple(sorted(result))
    if cache is not None:
        cache[key] = values
    return values
