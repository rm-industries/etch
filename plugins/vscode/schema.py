"""Normalize extension identifiers and one VS Code CLI target."""

import math
import re
from dataclasses import dataclass
from typing import Any

from etchlib.config import compose_defaults
from etchlib.providers.contracts import Context


@dataclass(frozen=True)
class Target:
    command: str
    profile: str
    timeout: float


def identifier(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("extension IDs must be publisher.extension strings")
    normalized = value.strip().lower()
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9-]*\.[a-z0-9][a-z0-9-]*", normalized
    ) or normalized.endswith(".vsix"):
        raise ValueError(
            "invalid Marketplace extension ID {!r}; paths, VSIX files and version pins are unsupported".format(
                value
            )
        )
    return normalized


def target(config: Any) -> Target:
    if not isinstance(config, dict) or set(config) - {"command", "profile", "timeout"}:
        raise ValueError("VS Code target accepts command, profile and timeout")
    command = config.get("command", "code")
    profile = config.get("profile", "")
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(ord(char) < 32 for char in command)
    ):
        raise ValueError("command must name one executable")
    if (
        not isinstance(profile, str)
        or any(ord(char) < 32 for char in profile)
        or (profile and not profile.strip())
    ):
        raise ValueError("profile must be a nonempty name when supplied")
    timeout = config.get("timeout", 120)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number of seconds")
    return Target(command, profile, float(timeout))


def action_options(config: Any, context: Context) -> tuple[Target, tuple[str, ...]]:
    if not isinstance(config, dict) or set(config) - {
        "extensions",
        "command",
        "profile",
        "timeout",
    }:
        raise ValueError(
            "vscode accepts extensions, command, profile and timeout; removal is unsupported"
        )
    values = compose_defaults(
        "vscode",
        dict(context.defaults.get("vscode", {})),
        config,
        ("command", "profile", "timeout"),
    )
    desired = values.pop("extensions", None)
    if not isinstance(desired, list):
        raise ValueError("vscode extensions must be a list")
    return target(values), tuple(sorted({identifier(value) for value in desired}))
