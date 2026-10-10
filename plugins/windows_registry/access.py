"""Native Registry access, imported only when running on Windows."""

import importlib
import platform
from typing import Any

from .schema import Preferences


def registry() -> Any:
    if platform.system() != "Windows":
        raise ValueError(
            "windows_registry is Windows-only; guard the module with when: {'os': 'windows'}"
        )
    return importlib.import_module("winreg")


def read(desired: Preferences) -> dict[str, tuple[Any, int]]:
    api = registry()
    current = {}
    try:
        with api.OpenKey(
            api.HKEY_CURRENT_USER,
            desired.key,
            0,
            api.KEY_QUERY_VALUE | api.KEY_WOW64_64KEY,
        ) as handle:
            for name in desired.values:
                try:
                    current[name] = api.QueryValueEx(handle, name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass
    except PermissionError as error:
        raise ValueError(
            "Registry read denied for HKEY_CURRENT_USER\\{}; check the key's permissions for this account".format(
                desired.key
            )
        ) from error
    return current


def write(desired: Preferences, names: tuple[str, ...]) -> None:
    api = registry()
    try:
        with api.CreateKeyEx(
            api.HKEY_CURRENT_USER,
            desired.key,
            0,
            api.KEY_SET_VALUE | api.KEY_WOW64_64KEY,
        ) as handle:
            for name in names:
                value = desired.values[name]
                api.SetValueEx(
                    handle, name, 0, getattr(api, value["type"]), value["data"]
                )
    except PermissionError as error:
        raise ValueError(
            "Registry write denied for HKEY_CURRENT_USER\\{}; check the key's permissions for this account; Etch does not elevate".format(
                desired.key
            )
        ) from error
