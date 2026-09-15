"""Conjoined version comparisons, with no wildcard or dependency solver syntax."""

import operator
import re
from typing import Union

from .parser import Version, parse_version

OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def matches(version: Union[str, Version], constraint: str) -> bool:
    value = version if isinstance(version, Version) else parse_version(version)
    if not isinstance(constraint, str) or not constraint.strip():
        raise ValueError("constraint must be a nonempty string")
    comparisons = []
    for part in constraint.split(","):
        match = re.fullmatch(r"\s*(==|!=|<=|>=|<|>)\s*(\S+)\s*", part)
        if match is None:
            raise ValueError("unsupported version constraint {!r}".format(part))
        operation, target = match.groups()
        comparisons.append((OPERATORS[operation], parse_version(target)))
    # Parse every term before evaluating; a false prefix must not hide invalid syntax.
    return all(operation(value, target) for operation, target in comparisons)
