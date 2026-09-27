"""Terminal presentation for human-facing CLI text."""

import os
import re
import sys
from typing import Optional, TextIO

_STATUS = re.compile(
    r"^(\s*(?:\S+:\s+)?)(CHANGE|RUN|SKIP|DEFERRED|CHANGED|UNCHANGED|SKIPPED|FAILED|BLOCKED|VALUE|UNAVAILABLE|Warning|Error|FAIL)(?=\b|:)"
)
_COLORS = {
    "CHANGE": "36",
    "RUN": "36",
    "CHANGED": "32",
    "VALUE": "32",
    "SKIP": "2",
    "SKIPPED": "2",
    "UNCHANGED": "2",
    "DEFERRED": "33",
    "BLOCKED": "33",
    "UNAVAILABLE": "33",
    "Warning": "33",
    "FAILED": "31",
    "FAIL": "31",
    "Error": "31",
}


def present(text: str, color: bool) -> str:
    """Color only known status labels; keep plain text identical otherwise."""
    if not color:
        return text

    def highlight(match: re.Match[str]) -> str:
        label = match.group(2)
        return "{}\x1b[{}m{}\x1b[0m".format(match.group(1), _COLORS[label], label)

    return "\n".join(_STATUS.sub(highlight, line) for line in text.split("\n"))


def write_output(text: str, stream: Optional[TextIO] = None) -> None:
    stream = stream or sys.stdout
    color = (
        stream.isatty()
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
    )
    stream.write(present(text, color) + "\n")
