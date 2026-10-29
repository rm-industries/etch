"""Presence-only Python distribution names and native uv target options."""

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


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", value
    ):
        raise ValueError(
            "uv tools must be distribution names; versions, extras, URLs, paths and flags are unsupported"
        )
    return re.sub(r"[-_.]+", "-", value).lower()


def target(config: Any) -> Target:
    if not isinstance(config, dict) or set(config) - {"command", "timeout"}:
        raise ValueError("uv target accepts command and timeout")
    command, timeout = config.get("command", "uv"), config.get("timeout", 600)
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(ord(char) < 32 for char in command)
    ):
        raise ValueError("command must name one executable")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive finite seconds")
    return Target(command, float(timeout))


def action_options(config: Any, context: Context) -> tuple[Target, tuple[str, ...]]:
    if not isinstance(config, dict) or set(config) - {"tools", "command", "timeout"}:
        raise ValueError(
            "uv accepts tools, command and timeout; version/Python selection, upgrades and removal are unsupported"
        )
    if "tools" not in config or not isinstance(config["tools"], list):
        raise ValueError("uv requires a tools list")
    values = compose_defaults(
        "uv", dict(context.defaults.get("uv", {})), config, ("command", "timeout")
    )
    tools = tuple(sorted({identifier(item) for item in values.pop("tools")}))
    return target(values), tools
