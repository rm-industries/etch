"""Presence-only package requests and one Homebrew CLI target."""

import math
import re
from dataclasses import dataclass
from typing import Any

from etchlib.config import compose_defaults
from etchlib.providers.contracts import Context


@dataclass(frozen=True)
class Target:
    command: str
    timeout: float


def identifier(value: object, kind: str) -> str:
    if not isinstance(value, str):
        raise ValueError("package names must be strings")
    name = value.strip().lower()
    parts = name.split("/")
    if (
        len(parts) not in (1, 3)
        or any(not re.fullmatch(r"[a-z0-9][a-z0-9+_.@-]*", part) for part in parts)
        or name.endswith((".rb", ".json"))
    ):
        raise ValueError(
            "invalid Homebrew package name {!r}; URLs and local files are unsupported".format(
                value
            )
        )
    prefix = "homebrew/core/" if kind == "formula" else "homebrew/cask/"
    return name[len(prefix) :] if name.startswith(prefix) else name


def target(config: Any) -> Target:
    if not isinstance(config, dict) or set(config) - {"command", "timeout"}:
        raise ValueError("Homebrew target accepts command and timeout")
    command, timeout = config.get("command", "brew"), config.get("timeout", 600)
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(ord(char) < 32 for char in command)
    ):
        raise ValueError("command must name one executable")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number of seconds")
    return Target(command, float(timeout))


def action_options(
    config: Any, context: Context
) -> tuple[Target, tuple[str, ...], tuple[str, ...]]:
    if not isinstance(config, dict) or set(config) - {
        "formulae",
        "casks",
        "command",
        "timeout",
    }:
        raise ValueError(
            "brew accepts formulae, casks, command and timeout; upgrades/removal are unsupported"
        )
    if not {"formulae", "casks"} & set(config):
        raise ValueError("brew requires formulae or casks")
    values = compose_defaults(
        "brew", dict(context.defaults.get("brew", {})), config, ("command", "timeout")
    )
    packages = []
    for field, kind in (("formulae", "formula"), ("casks", "cask")):
        requested = values.pop(field, [])
        if not isinstance(requested, list):
            raise ValueError(field + " must be a list")
        packages.append(tuple(sorted({identifier(name, kind) for name in requested})))
    return target(values), packages[0], packages[1]
