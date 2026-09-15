"""Execution option validation shared by local commands and installers."""

import math
from typing import Any, Mapping

COMMON = ("description", "quiet", "stdin", "sudo", "env", "check", "timeout")


def validate_options(options: Mapping[str, Any]) -> None:
    for key in ("quiet", "stdin", "sudo"):
        if type(options.get(key, False)) is not bool:
            raise ValueError("{} must be boolean".format(key))
    if "description" in options and (
        not isinstance(options["description"], str)
        or not options["description"].strip()
    ):
        raise ValueError("description must be a nonempty string")
    timeout = options.get("timeout", 300)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
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
            kind not in ("command", "path_exists", "file_exists", "directory_exists")
            or not isinstance(query, str)
            or not query
            or "\x00" in query
        ):
            raise ValueError("unsupported check predicate")
