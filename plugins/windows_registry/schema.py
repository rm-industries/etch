"""Validate explicit typed values in one current-user Registry key."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Preferences:
    key: str
    values: dict[str, dict[str, Any]]


def preferences(config: Any) -> Preferences:
    if not isinstance(config, dict) or set(config) != {"hive", "key", "values"}:
        raise ValueError("windows_registry requires hive, key and values")
    if config["hive"] != "HKEY_CURRENT_USER":
        raise ValueError(
            "windows_registry supports HKEY_CURRENT_USER only; system hives and elevation are unsupported"
        )
    key = config["key"]
    if (
        not isinstance(key, str)
        or not key
        or any(not part or part in (".", "..") for part in key.split("\\"))
        or any(ord(c) < 32 for c in key)
        or "/" in key
    ):
        raise ValueError(
            "windows_registry key must be a relative backslash-separated Registry path"
        )
    values = config["values"]
    if not isinstance(values, dict) or not values:
        raise ValueError("windows_registry values must be a nonempty dictionary")
    names = set()
    for name, value in values.items():
        if not isinstance(name, str) or not name or any(ord(c) < 32 for c in name):
            raise ValueError(
                "windows_registry requires named values; default values are unsupported"
            )
        if name.casefold() in names:
            raise ValueError(
                "windows_registry value names must be unique ignoring case"
            )
        names.add(name.casefold())
        if not isinstance(value, dict) or set(value) != {"type", "data"}:
            raise ValueError(
                "each Registry value requires type and data; deletion is unsupported"
            )
        kind, data = value["type"], value["data"]
        valid = False
        if kind in ("REG_SZ", "REG_EXPAND_SZ"):
            valid = isinstance(data, str) and "\x00" not in data
        elif kind in ("REG_DWORD", "REG_QWORD"):
            valid = type(data) is int and 0 <= data < 2 ** (
                32 if kind == "REG_DWORD" else 64
            )
        elif kind == "REG_MULTI_SZ":
            valid = isinstance(data, list) and all(
                isinstance(item, str) and item and "\x00" not in item for item in data
            )
        if not valid:
            raise ValueError(
                "unsupported Registry type or invalid data for {!r}".format(name)
            )
    return Preferences(key, {name: dict(value) for name, value in values.items()})
