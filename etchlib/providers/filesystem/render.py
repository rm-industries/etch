"""Human descriptions for filesystem actions."""

from pathlib import Path
from typing import Iterable


def describe_links(paths: Iterable[Path], verb: str) -> str:
    items = tuple(paths)
    if len(items) == 1:
        return "{}: {}".format(verb, items[0])
    return "{} {} paths:\n{}".format(
        verb, len(items), "\n".join("- {}".format(path) for path in items)
    )
