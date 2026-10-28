"""npm-specific global targeting, validated inventory and snapshot caching."""

import hashlib
import json
import os
from pathlib import Path
from typing import cast

from etchlib.providers import native
from etchlib.providers.contracts import Context

from .schema import Target, identifier


def environment_key() -> str:
    # Fingerprint all inherited configuration without retaining credentials in cache keys.
    return hashlib.sha256(repr(sorted(os.environ.items())).encode()).hexdigest()


def locate(target: Target, context: Context) -> str:
    executable = native.locate(target.command, context.module_root)
    if executable is None:
        raise ValueError(
            "npm command {!r} is unavailable; install Node/npm and expose its CLI first".format(
                target.command
            )
        )
    return executable


def run(
    executable: str, target: Target, args: tuple[str, ...], context: Context
) -> str:
    return native.run(
        executable, args, cwd=context.module_root, timeout=target.timeout, label="npm"
    )


def cache_key(
    kind: str, executable: str, target: Target, context: Context, prefix: str = ""
) -> tuple[str, ...]:
    return (
        "npm." + kind,
        executable,
        target.prefix or "",
        prefix,
        str(target.timeout),
        str(context.module_root),
        environment_key(),
    )


def global_prefix(executable: str, target: Target, context: Context) -> str:
    key = cache_key("prefix", executable, target, context)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(str, cache[key])
    args: tuple[str, ...] = ("prefix", "--global")
    if target.prefix is not None:
        args += ("--prefix=" + target.prefix,)
    output = run(executable, target, args, context).strip()
    if (
        not output
        or any(ord(char) < 32 for char in output)
        or not Path(output).is_absolute()
    ):
        raise ValueError(
            "npm returned an invalid global prefix; expected one absolute directory path"
        )
    prefix = str(Path(output).resolve())
    if target.prefix is not None and prefix != target.prefix:
        raise ValueError("npm did not honor the requested global prefix")
    if cache is not None:
        cache[key] = prefix
    return prefix


def installed(
    executable: str, target: Target, prefix: str, context: Context
) -> tuple[str, ...]:
    key = cache_key("inventory", executable, target, context, prefix)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(tuple[str, ...], cache[key])
    # A fresh Unix prefix has no global root yet; npm ls otherwise returns ENOENT.
    try:
        (Path(prefix) / "lib").stat()
    except FileNotFoundError:
        if cache is not None:
            cache[key] = ()
        return ()
    output = run(
        executable,
        target,
        (
            "ls",
            "--global",
            "--prefix=" + prefix,
            "--depth=0",
            "--json",
            "--long=false",
            "--package-lock-only=false",
            "--link=false",
        ),
        context,
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("npm returned invalid JSON inventory") from exc
    if not isinstance(value, dict) or "error" in value or value.get("problems"):
        raise ValueError("npm inventory contains errors or dependency problems")
    if "dependencies" not in value and set(value) - {"name", "version", "resolved"}:
        raise ValueError("npm inventory is missing its dependencies object")
    if any(
        not isinstance(value[key], str)
        for key in ("name", "version", "resolved")
        if key in value
    ):
        raise ValueError("npm inventory metadata must contain strings")
    rows = value.get("dependencies", {})
    if not isinstance(rows, dict):
        raise ValueError("npm inventory dependencies must be an object")
    names = []
    for name, row in rows.items():
        identifier(name)
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("version"), str)
            or not row["version"].strip()
            or row.get("missing")
            or row.get("invalid")
            or row.get("error")
            or row.get("problems")
        ):
            raise ValueError(
                "npm inventory has an invalid or missing package entry: " + name
            )
        names.append(name)
    result = tuple(sorted(names))
    if cache is not None:
        cache[key] = result
    return result
