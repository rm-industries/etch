"""Validate installer configuration without downloading or executing code."""

import platform
from dataclasses import dataclass
from pathlib import Path
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
        COMMON + ("shell", "tls", "download_timeout", "expand_home"),
    )
    if (
        set(values)
        - set(COMMON)
        - {"url", "shell", "args", "tls", "sha256", "download_timeout", "expand_home"}
    ):
        raise ValueError("unknown installer options")
    if type(values.get("expand_home", False)) is not bool:
        raise ValueError("expand_home must be boolean")
    validate_options(values)
    transfer = normalize_transfer(
        {
            key: values[key]
            for key in ("url", "tls", "sha256", "download_timeout")
            if key in values
        },
        context,
    )
    shell = values.get("shell", "pwsh" if platform.system() == "Windows" else "/bin/sh")
    if not isinstance(shell, str) or not shell.strip() or "\x00" in shell:
        raise ValueError("installer shell must name one executable")
    if platform.system() == "Windows" and shell not in ("pwsh", "powershell.exe"):
        raise ValueError(
            "Windows installers support PowerShell scripts only; shell must be pwsh or powershell.exe"
        )
    args = arguments(values.get("args", []), allow_empty=True)
    if values.get("expand_home", False):
        home = str(Path.home())

        def expand(value: str) -> str:
            if (
                value == "~"
                or value.startswith("~/")
                or (platform.system() == "Windows" and value.startswith("~\\"))
            ):
                return home + value[1:]
            return value

        args = tuple(expand(value) for value in args)
        if "env" in values:
            values["env"] = {
                name: expand(value) for name, value in values["env"].items()
            }
    return Installer(transfer, shell, args, values)
