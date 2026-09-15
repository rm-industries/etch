"""Validate installer configuration without downloading or executing code."""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from etchlib.config import Module, compose_defaults
from etchlib.providers.commands.options import COMMON, validate_options
from etchlib.providers.commands.schema import arguments
from etchlib.providers.contracts import Context


@dataclass(frozen=True)
class Installer:
    url: str
    shell: str
    args: tuple[str, ...]
    options: dict[str, Any]
    verify: bool
    ca_file: Optional[Path]
    sha256: Optional[str]
    download_timeout: float


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
    url = values.get("url")
    if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise ValueError("installer URL must be an HTTPS URL without whitespace")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("installer requires HTTPS without credentials or fragments")
    # Accessing port also rejects malformed or out-of-range ports before networking.
    if parsed.port == 0:
        raise ValueError("installer URL port must be positive")
    shell = values.get("shell", "/bin/sh")
    if not isinstance(shell, str) or not shell.strip() or "\x00" in shell:
        raise ValueError("installer shell must name one executable")
    args = arguments(values.get("args", []), allow_empty=True)
    checksum = values.get("sha256")
    if checksum is not None and (
        not isinstance(checksum, str)
        or re.fullmatch(r"[0-9a-fA-F]{64}", checksum) is None
    ):
        raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
    tls = values.get("tls", {})
    if not isinstance(tls, dict) or set(tls) - {"verify", "ca_file"}:
        raise ValueError("tls accepts verify and ca_file")
    verify = tls.get("verify", True)
    if type(verify) is not bool:
        raise ValueError("tls.verify must be boolean")
    ca_file = None
    if "ca_file" in tls:
        if not verify:
            raise ValueError("ca_file cannot be combined with disabled verification")
        ca_file = Module(context.module_name, context.module_root, {}).asset(
            tls["ca_file"]
        )
        if not ca_file.is_file():
            raise ValueError("ca_file must be a module-owned file")
    timeout = values.get("download_timeout", 30)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("download_timeout must be positive finite seconds")
    return Installer(
        url,
        shell,
        args,
        values,
        verify,
        ca_file,
        checksum.lower() if checksum is not None else None,
        float(timeout),
    )
