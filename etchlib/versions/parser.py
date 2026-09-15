"""Parse and compare numeric tool versions with single-letter patch suffixes."""

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Tuple


@total_ordering
@dataclass(frozen=True)
class Version:
    numbers: Tuple[int, ...]
    suffix: str = ""
    suffix_number: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.numbers, tuple)
            or not self.numbers
            or any(type(n) is not int or n < 0 for n in self.numbers)
        ):
            raise ValueError("version components must be nonnegative integers")
        if (
            not isinstance(self.suffix, str)
            or re.fullmatch(r"[a-z]?", self.suffix) is None
        ):
            raise ValueError("version suffix must be a single lowercase letter")
        if (
            type(self.suffix_number) is not int
            or self.suffix_number < 0
            or (not self.suffix and self.suffix_number)
        ):
            raise ValueError("invalid patch suffix number")
        numbers = self.numbers
        while len(numbers) > 1 and numbers[-1] == 0:
            numbers = numbers[:-1]
        object.__setattr__(self, "numbers", numbers)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.numbers, self.suffix, self.suffix_number) < (
            other.numbers,
            other.suffix,
            other.suffix_number,
        )


def parse_version(text: str) -> Version:
    if not isinstance(text, str):
        raise ValueError("version must be a string")
    match = re.fullmatch(r"v?([0-9]+(?:\.[0-9]+)*)([a-z]?)([0-9]*)", text.strip())
    if match is None:
        raise ValueError("unsupported version {!r}".format(text))
    numeric, suffix, patch = match.groups()
    numbers = [int(part) for part in numeric.split(".")]
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    return Version(tuple(numbers), suffix, int(patch or "0"))


def extract_version(output: str) -> str:
    """Read the first version-like token on the first nonempty output line."""
    line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    try:
        parse_version(line)
        return line.removeprefix("v")
    except ValueError:
        pass
    # Consume unsupported suffix syntax too, so 1.2.3-rc1 cannot become 1.2.3.
    match = re.search(
        r"(?<![A-Za-z0-9.+-])v?[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.+-]*)", line
    )
    if match is None:
        raise ValueError("no supported version in first output line")
    token = match.group()
    parse_version(token)
    return token.removeprefix("v")
