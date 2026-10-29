"""Presence-only package IDs and one explicit WinGet source."""

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
    source: str


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._+-]*", value
    ):
        raise ValueError(
            "winget requires package IDs; versions, URLs, paths and flags are unsupported"
        )
    return value


def target(config: Any) -> Target:
    if not isinstance(config, dict) or set(config) - {"command", "timeout", "source"}:
        raise ValueError("winget target accepts command, timeout and source")
    command = config.get("command", "winget")
    timeout = config.get("timeout", 600)
    source = config.get("source", "winget")
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(ord(c) < 32 for c in command)
    ):
        raise ValueError("command must name one executable")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive finite seconds")
    if not isinstance(source, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*", source
    ):
        raise ValueError("source must be one configured WinGet source name")
    return Target(command, float(timeout), source)


def action_options(config: Any, context: Context) -> tuple[Target, tuple[str, ...]]:
    if not isinstance(config, dict) or set(config) - {
        "packages",
        "command",
        "timeout",
        "source",
    }:
        raise ValueError(
            "winget accepts packages, command, timeout and source; upgrades/removal are unsupported"
        )
    if "packages" not in config or not isinstance(config["packages"], list):
        raise ValueError("winget requires a packages list")
    values = compose_defaults(
        "winget",
        dict(context.defaults.get("winget", {})),
        config,
        ("command", "timeout", "source"),
    )
    packages = tuple(sorted({identifier(item) for item in values.pop("packages")}))
    return target(values), packages
