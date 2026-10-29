"""Native uv directories, complete inventory validation and snapshot caching."""

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast

from etchlib.providers import native
from etchlib.providers.contracts import Context

from .schema import Target, identifier


@dataclass(frozen=True)
class Directories:
    tools: str
    executables: str


def environment_key() -> str:
    return hashlib.sha256(repr(sorted(os.environ.items())).encode()).hexdigest()


def locate(target: Target, context: Context) -> Optional[str]:
    return native.locate(target.command, context.module_root)


def capture(
    executable: str,
    target: Target,
    args: tuple[str, ...],
    context: Context,
    paths: Optional[Directories] = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if paths is not None:
        env.update(UV_TOOL_DIR=paths.tools, UV_TOOL_BIN_DIR=paths.executables)
    return native.capture(
        executable,
        ("--color", "never", "--no-progress", *args),
        cwd=context.module_root,
        timeout=target.timeout,
        label="uv",
        env=env,
    )


def _key(
    kind: str, executable: str, target: Target, context: Context
) -> tuple[str, ...]:
    return (
        "uv." + kind,
        executable,
        str(target.timeout),
        str(context.module_root),
        environment_key(),
    )


def directories(executable: str, target: Target, context: Context) -> Directories:
    key = _key("directories", executable, target, context)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(Directories, cache[key])
    values = []
    for args in (("tool", "dir"), ("tool", "dir", "--bin")):
        result = capture(executable, target, args, context)
        value = result.stdout.strip()
        if (
            result.stderr.strip()
            or not value
            or any(ord(char) < 32 for char in value)
            or not Path(value).is_absolute()
        ):
            raise ValueError(
                "uv returned an invalid tool directory or directory diagnostic; expected one absolute path"
            )
        values.append(str(Path(value).resolve()))
    paths = Directories(*values)
    if cache is not None:
        cache[key] = paths
    return paths


def installed(
    executable: str, target: Target, paths: Directories, context: Context
) -> tuple[str, ...]:
    key = _key("inventory", executable, target, context) + (
        paths.tools,
        paths.executables,
    )
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(tuple[str, ...], cache[key])
    result = capture(executable, target, ("tool", "list"), context, paths)
    diagnostic = result.stderr.strip()
    if diagnostic and (diagnostic != "No tools installed" or result.stdout.strip()):
        # uv can skip damaged tools and still exit zero; never treat that as absence.
        raise ValueError(
            "uv inventory contains diagnostics; inspect `uv tool list` and repair its tool environments before applying"
        )
    names = set()
    current = None
    has_executable = False
    for line in result.stdout.splitlines():
        if any(ord(char) < 32 or ord(char) == 127 for char in line):
            raise ValueError("invalid control characters in uv inventory")
        if line.startswith("- "):
            if current is None or not line[2:].strip():
                raise ValueError("invalid uv executable inventory row")
            has_executable = True
            continue
        match = re.fullmatch(r"(\S+) v([0-9][A-Za-z0-9.!+_-]*)", line)
        if match is None or (current is not None and not has_executable):
            raise ValueError(
                "invalid uv tool inventory; expected a tool/version followed by executable names"
            )
        current = identifier(match.group(1))
        if current in names:
            raise ValueError("duplicate uv tool inventory identity: " + current)
        names.add(current)
        has_executable = False
    if current is not None and not has_executable:
        raise ValueError("uv inventory lists a tool without executables")
    values = tuple(sorted(names))
    if cache is not None:
        cache[key] = values
    return values
