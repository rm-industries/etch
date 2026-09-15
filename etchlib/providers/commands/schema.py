"""Normalize command options without executing them."""

from typing import Any

from etchlib.config import Module, compose_defaults
from etchlib.providers.contracts import Context

from .options import COMMON, validate_options


def normalize(name: str, config: Any, context: Context) -> tuple[dict[str, Any], ...]:
    values = config if name == "shell" and isinstance(config, list) else [config]
    if not values:
        raise ValueError("shell requires at least one command")
    result = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("{} entries must be option dictionaries".format(name))
        options = compose_defaults(name, context.defaults.get(name, {}), value, COMMON)
        allowed = set(COMMON) | ({"command"} if name == "shell" else {"path", "args"})
        if set(options) - allowed:
            raise ValueError("unknown {} options".format(name))
        validate_options(options)
        argv: tuple[str, ...]
        if name == "shell":
            command = options.get("command")
            if isinstance(command, str):
                if not command.strip() or "\x00" in command:
                    raise ValueError("shell command cannot be empty")
                argv = ("/bin/sh", "-c", command)
            else:
                argv = arguments(command, allow_empty=False)
        else:
            module = Module(context.module_name, context.module_root, {})
            script = module.asset(options.get("path"))
            argv = (str(script),) + arguments(options.get("args", []), allow_empty=True)
        options["argv"] = argv
        options["provider"] = name
        result.append(options)
    return tuple(result)


def arguments(value: Any, allow_empty: bool) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or any(not isinstance(v, str) or "\x00" in v for v in value)
    ):
        raise ValueError("command/args must be an argument list")
    if value and not allow_empty and not value[0]:
        raise ValueError("executable cannot be empty")
    return tuple(value)
