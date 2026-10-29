"""Machine-readable WinGet inventory, scoped to one planning snapshot."""

import json
import tempfile
from pathlib import Path
from typing import cast

from etchlib.providers import native
from etchlib.providers.contracts import Context

from .schema import Target, identifier

EXPORT_LIMIT = 16 * 1024 * 1024


def locate(options: Target, context: Context) -> str:
    executable = native.locate(options.command, context.module_root)
    if executable is None:
        raise ValueError(
            "winget command {!r} is unavailable; install Windows App Installer first".format(
                options.command
            )
        )
    return executable


def run(
    executable: str, options: Target, args: tuple[str, ...], context: Context
) -> str:
    return native.capture(
        executable,
        args,
        cwd=context.module_root,
        timeout=options.timeout,
        label="winget",
    ).stdout


def installed(executable: str, options: Target, context: Context) -> tuple[str, ...]:
    key = (
        "winget.inventory",
        executable,
        options.source.casefold(),
        str(options.timeout),
        str(context.module_root),
    )
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(tuple[str, ...], cache[key])
    # Close the file before WinGet opens it; Windows cannot reopen a live NamedTemporaryFile.
    with tempfile.TemporaryDirectory(prefix="etch-winget-") as directory:
        path = Path(directory) / "packages.json"
        run(
            executable,
            options,
            (
                "export",
                "--output",
                str(path),
                "--source",
                options.source,
                "--disable-interactivity",
            ),
            context,
        )
        try:
            with path.open("rb") as stream:
                data = stream.read(EXPORT_LIMIT + 1)
            if len(data) > EXPORT_LIMIT:
                raise ValueError(
                    "winget inventory exceeds {} bytes".format(EXPORT_LIMIT)
                )
            value = json.loads(data.decode("utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "winget returned unreadable or invalid JSON inventory"
            ) from exc
    if not isinstance(value, dict) or not isinstance(value.get("Sources"), list):
        raise ValueError("winget inventory requires a Sources list")
    names = set()
    for source in value["Sources"]:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("SourceDetails"), dict)
            or not isinstance(source["SourceDetails"].get("Name"), str)
            or source["SourceDetails"]["Name"].casefold() != options.source.casefold()
            or not isinstance(source.get("Packages"), list)
        ):
            raise ValueError("winget inventory has invalid source or package data")
        for row in source["Packages"]:
            if not isinstance(row, dict):
                raise ValueError("winget inventory package entries must be objects")
            names.add(identifier(row.get("PackageIdentifier")))
    result = tuple(sorted(names))
    if cache is not None:
        cache[key] = result
    return result
