"""Strict registry package names and one effective global npm target."""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from etchlib.config import compose_defaults
from etchlib.providers.contracts import Context


@dataclass(frozen=True)
class Target:
    command: str
    timeout: float
    prefix: Optional[str]


def identifier(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 214
        or value in ("node_modules", "favicon.ico")
        or value.endswith((".tar", ".tar.gz", ".tgz"))
        or not re.fullmatch(r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*", value)
    ):
        raise ValueError(
            "npm packages must be simple registry names or @scope/name; versions, URLs, paths and flags are unsupported"
        )
    return value


def target(config: Any, context: Context) -> Target:
    if not isinstance(config, dict) or set(config) - {"command", "timeout", "prefix"}:
        raise ValueError("npm target accepts command, timeout and prefix")
    command, timeout = config.get("command", "npm"), config.get("timeout", 600)
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(ord(char) < 32 for char in command)
    ):
        raise ValueError("command must name one executable")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive finite seconds")
    prefix = None
    if "prefix" in config:
        value = config["prefix"]
        if (
            not isinstance(value, str)
            or not value.strip()
            or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("prefix must be a nonempty directory path")
        path = Path(value).expanduser()
        prefix = str(
            (path if path.is_absolute() else context.module_root / path).resolve()
        )
    return Target(command, float(timeout), prefix)


def action_options(config: Any, context: Context) -> tuple[Target, tuple[str, ...]]:
    if not isinstance(config, dict) or set(config) - {
        "packages",
        "command",
        "timeout",
        "prefix",
    }:
        raise ValueError(
            "npm accepts packages, command, timeout and prefix; upgrades/removal are unsupported"
        )
    if "packages" not in config or not isinstance(config["packages"], list):
        raise ValueError("npm requires a packages list")
    values = compose_defaults(
        "npm",
        dict(context.defaults.get("npm", {})),
        config,
        ("command", "timeout", "prefix"),
    )
    packages = tuple(sorted({identifier(item) for item in values.pop("packages")}))
    return target(values, context), packages
