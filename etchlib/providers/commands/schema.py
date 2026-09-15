"""Normalize command options without executing them."""

import math
from typing import Any

from etchlib.config import Module, compose_defaults
from etchlib.providers.contracts import Context

COMMON = ("description", "quiet", "stdin", "sudo", "env", "check", "timeout")


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
        for key in ("quiet", "stdin", "sudo"):
            if type(options.get(key, False)) is not bool:
                raise ValueError("{} must be boolean".format(key))
        if "description" in options and (
            not isinstance(options["description"], str)
            or not options["description"].strip()
        ):
            raise ValueError("description must be a nonempty string")
        timeout = options.get("timeout", 300)
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be positive finite seconds")
        env = options.get("env", {})
        if not isinstance(env, dict) or any(
            not isinstance(k, str)
            or not k
            or "=" in k
            or "\x00" in k
            or not isinstance(v, str)
            or "\x00" in v
            for k, v in env.items()
        ):
            raise ValueError("env must map valid variable names to strings")
        check = options.get("check")
        if check is not None:
            if not isinstance(check, dict) or len(check) != 1:
                raise ValueError("check requires one presence predicate")
            kind, query = next(iter(check.items()))
            if (
                kind
                not in ("command", "path_exists", "file_exists", "directory_exists")
                or not isinstance(query, str)
                or not query
                or "\x00" in query
            ):
                raise ValueError("unsupported check predicate")
        argv: tuple[str, ...]
        if name == "shell":
            command = options.get("command")
            if isinstance(command, str):
                if not command.strip() or "\x00" in command:
                    raise ValueError("shell command cannot be empty")
                argv = ("/bin/sh", "-c", command)
            else:
                argv = _argv(command, allow_empty=False)
        else:
            module = Module(context.module_name, context.module_root, {})
            script = module.asset(options.get("path"))
            argv = (str(script),) + _argv(options.get("args", []), allow_empty=True)
        options["argv"] = argv
        options["provider"] = name
        result.append(options)
    return tuple(result)


def _argv(value: Any, allow_empty: bool) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or any(not isinstance(v, str) or "\x00" in v for v in value)
    ):
        raise ValueError("command/args must be an argument list")
    if value and not allow_empty and not value[0]:
        raise ValueError("executable cannot be empty")
    return tuple(value)
