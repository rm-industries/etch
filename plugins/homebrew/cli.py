"""Homebrew policy and inventory over shared bounded native execution."""

import os
from typing import Optional, cast

from etchlib.providers import native
from etchlib.providers.contracts import Context

from .schema import Target, identifier


def locate(target: Target, context: Context) -> Optional[str]:
    return native.locate(target.command, context.module_root)


def run(
    executable: str, target: Target, args: tuple[str, ...], context: Context
) -> str:
    env = dict(os.environ)
    env.update(
        {
            name: "1"
            for name in (
                "HOMEBREW_NO_AUTO_UPDATE",
                "HOMEBREW_NO_INSTALL_UPGRADE",
                "HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK",
                "HOMEBREW_NO_INSTALL_CLEANUP",
            )
        }
    )
    return native.capture(
        executable,
        args,
        cwd=context.module_root,
        timeout=target.timeout,
        label="Homebrew",
        env=env,
    ).stdout


def installed(
    executable: str, target: Target, kind: str, context: Context
) -> tuple[str, ...]:
    key = ("homebrew.inventory", executable, str(target.timeout), kind)
    cache = context.inspection_cache
    if cache is not None and key in cache:
        return cast(tuple[str, ...], cache[key])
    output = run(
        executable, target, ("list", "--" + kind, "--full-name", "-1"), context
    )
    values = tuple(
        sorted({identifier(line, kind) for line in output.splitlines() if line.strip()})
    )
    if cache is not None:
        cache[key] = values
    return values
