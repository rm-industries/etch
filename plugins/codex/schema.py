"""Bounded native marketplace sources, plugin selectors and CLI options."""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from etchlib.config import compose_defaults
from etchlib.providers.contracts import Context


@dataclass(frozen=True)
class Target:
    command: str
    timeout: float


def name(value: Any) -> str:
    if (
        not isinstance(value, str)
        or value in (".", "..")
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)
    ):
        raise ValueError("plugin and marketplace names must be simple identifiers")
    return value


def selector(value: Any) -> str:
    if not isinstance(value, str) or value.count("@") != 1:
        raise ValueError("plugins must use plugin@marketplace selectors")
    plugin, market = value.split("@")
    return name(plugin) + "@" + name(market)


def source(value: Any, context: Context) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise ValueError("marketplace source must be a nonempty string")
    if re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", value
    ) and not value.endswith("/.."):
        value = "https://github.com/" + value
    if value.startswith("https://"):
        url = urlsplit(str(value))
        if (
            not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or not url.path.strip("/")
            or any(char.isspace() for char in value)
            or any(part in (".", "..") for part in url.path.split("/"))
        ):
            raise ValueError(
                "marketplace HTTPS Git URLs require a path and no credentials, query or fragment"
            )
        if url.port is not None and url.port == 0:
            raise ValueError("marketplace URL port must be positive")
        path = url.path
        if url.hostname.lower() == "github.com":
            path = path.rstrip("/")
            if path.endswith(".git"):
                path = path[:-4]
            path = path.lower() + ".git"
        return urlunsplit(("https", url.netloc.lower(), path, "", ""))
    if (
        value.startswith(("./", "../", "~/", "/", ".\\", "..\\"))
        or Path(value).is_absolute()
    ):
        local_path = Path(value).expanduser()
        return str(
            (
                local_path
                if local_path.is_absolute()
                else context.module_root / local_path
            ).resolve()
        )
    raise ValueError(
        "marketplace sources must be owner/repo, credential-free HTTPS Git URLs or explicit local paths; refs and SSH are unsupported"
    )


def target(config: Any) -> Target:
    if not isinstance(config, dict) or set(config) - {"command", "timeout"}:
        raise ValueError("Codex target accepts command and timeout")
    command = config.get("command", "codex")
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(ord(char) < 32 for char in command)
    ):
        raise ValueError("command must name one executable")
    timeout = config.get("timeout", 120)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive finite seconds")
    return Target(command, float(timeout))


def action_options(
    config: Any, context: Context
) -> tuple[Target, tuple[str, ...], tuple[str, ...]]:
    if not isinstance(config, dict) or set(config) - {
        "marketplaces",
        "plugins",
        "command",
        "timeout",
    }:
        raise ValueError("codex accepts marketplaces, plugins, command and timeout")
    values = compose_defaults(
        "codex", dict(context.defaults.get("codex", {})), config, ("command", "timeout")
    )
    markets, plugins = values.pop("marketplaces", []), values.pop("plugins", [])
    if not isinstance(markets, list) or not isinstance(plugins, list):
        raise ValueError("marketplaces and plugins must be lists")
    return (
        target(values),
        tuple(dict.fromkeys(source(item, context) for item in markets)),
        tuple(sorted({selector(item) for item in plugins})),
    )
