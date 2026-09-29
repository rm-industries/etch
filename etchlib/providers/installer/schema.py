"""Validate installer configuration without downloading or executing code."""

from dataclasses import dataclass
from typing import Any

from etchlib.config import compose_defaults
from etchlib.providers.commands.options import COMMON, validate_options
from etchlib.providers.commands.schema import arguments
from etchlib.providers.contracts import Context
from etchlib.providers.download.schema import Transfer, normalize_transfer


@dataclass(frozen=True)
class Installer:
    transfer: Transfer
    shell: str
    args: tuple[str, ...]
    options: dict[str, Any]


def normalize(config: Any, context: Context) -> Installer:
    if not isinstance(config, dict):
        raise ValueError("installer expects an options dictionary")
    values = compose_defaults(
        "installer",
        context.defaults.get("installer", {}),
        config,
        COMMON + ("shell", "tls", "download_timeout"),
    )
    if (
        set(values)
        - set(COMMON)
        - {"url", "shell", "args", "tls", "sha256", "download_timeout"}
    ):
        raise ValueError("unknown installer options")
    validate_options(values)
    transfer = normalize_transfer(
        {
            key: values[key]
            for key in ("url", "tls", "sha256", "download_timeout")
            if key in values
        },
        context,
    )
    shell = values.get("shell", "/bin/sh")
    if not isinstance(shell, str) or not shell.strip() or "\x00" in shell:
        raise ValueError("installer shell must name one executable")
    args = arguments(values.get("args", []), allow_empty=True)
    return Installer(transfer, shell, args, values)
