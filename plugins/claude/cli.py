"""Claude JSON commands using shared bounded native execution."""

import json
from typing import Any, Optional

from etchlib.providers import native
from etchlib.providers.contracts import Context

from .schema import Target


def locate(target: Target, context: Context) -> Optional[str]:
    return native.locate(target.command, context.module_root)


def run(
    executable: str, target: Target, args: tuple[str, ...], context: Context
) -> str:
    return native.capture(
        executable,
        args,
        cwd=context.module_root,
        timeout=target.timeout,
        label="Claude",
    ).stdout


def document(
    executable: str, target: Target, args: tuple[str, ...], context: Context
) -> list[Any]:
    try:
        value = json.loads(run(executable, target, args + ("--json",), context))
    except json.JSONDecodeError as exc:
        raise ValueError("Claude returned invalid JSON inventory/result") from exc
    if not isinstance(value, list):
        raise ValueError("Claude JSON inventory/result must be an array")
    return value
