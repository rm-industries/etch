"""Read and write current-user preferences through macOS `defaults`."""

import plistlib
import subprocess
from typing import Any

from .schema import Value

_DEFAULTS = "/usr/bin/defaults"


def _run(*args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            [_DEFAULTS, *args], capture_output=True, check=False, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("macOS defaults command failed: {}".format(exc)) from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            "macOS defaults command failed: {}".format(detail or result.returncode)
        )
    return result


def read_domain(domain: str) -> dict[str, Any]:
    try:
        values = plistlib.loads(_run("export", domain, "-").stdout)
    except (plistlib.InvalidFileException, ValueError, TypeError) as exc:
        raise ValueError(
            "cannot read macOS preferences domain {!r}: {}".format(domain, exc)
        ) from exc
    if not isinstance(values, dict):
        raise ValueError(
            "macOS preferences domain {!r} is not a dictionary".format(domain)
        )
    return values


def write_key(domain: str, key: str, value: Value) -> None:
    if type(value) is bool:
        kind, rendered = "-bool", "true" if value else "false"
    elif type(value) is int:
        kind, rendered = "-int", str(value)
    elif type(value) is float:
        kind, rendered = "-float", repr(value)
    else:
        kind, rendered = "-string", str(value)
    _run("write", domain, key, kind, rendered)
