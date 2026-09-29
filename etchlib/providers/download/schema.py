"""Shared HTTPS transfer options for download and installer actions."""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

from etchlib.config import Module
from etchlib.providers.contracts import Context


@dataclass(frozen=True)
class Transfer:
    url: str
    verify: bool
    ca_file: Optional[Path]
    sha256: Optional[str]
    download_timeout: float


def normalize_transfer(values: Mapping[str, Any], context: Context) -> Transfer:
    if set(values) - {"url", "tls", "sha256", "download_timeout"}:
        raise ValueError("unknown download options")
    url = values.get("url")
    if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise ValueError("download URL must be an HTTPS URL without whitespace")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("download requires HTTPS without credentials or fragments")
    if parsed.port == 0:
        raise ValueError("download URL port must be positive")
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
    return Transfer(
        url,
        verify,
        ca_file,
        checksum.lower() if checksum is not None else None,
        float(timeout),
    )
