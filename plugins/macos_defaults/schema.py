"""Validate one current-user preferences domain and its declared keys."""

import math
import re
from dataclasses import dataclass
from typing import Any, Union

Value = Union[str, bool, int, float]


@dataclass(frozen=True)
class Preferences:
    domain: str
    values: dict[str, Value]


def preferences(config: Any) -> Preferences:
    if not isinstance(config, dict) or set(config) != {"domain", "values"}:
        raise ValueError("macos_defaults requires domain and values")
    domain = config["domain"]
    if not isinstance(domain, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*", domain
    ):
        raise ValueError("macos_defaults domain must be a preference domain name")
    values = config["values"]
    if not isinstance(values, dict) or not values:
        raise ValueError("macos_defaults values must be a nonempty dictionary")
    for key, value in values.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or key.startswith("-")
            or any(ord(char) < 32 or ord(char) == 127 for char in key)
        ):
            raise ValueError("macos_defaults keys must be nonempty preference names")
        if type(value) not in (str, bool, int, float):
            raise ValueError(
                "macos_defaults value for {!r} has unsupported type".format(key)
            )
        if type(value) is float and not math.isfinite(value):
            raise ValueError("macos_defaults value for {!r} must be finite".format(key))
    return Preferences(domain, dict(values))
