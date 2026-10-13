"""Bounded failure diagnostics from a temporary command-output spool."""

import os
from typing import BinaryIO

LIMIT = 16 * 1024


def diagnostic(message: str, output: BinaryIO) -> str:
    output.seek(0, os.SEEK_END)
    size = output.tell()
    output.seek(max(0, size - LIMIT))
    detail = output.read(LIMIT).decode("utf-8", errors="replace").strip()
    if not detail:
        return message
    label = "Command output (last 16 KiB)" if size > LIMIT else "Command output"
    return "{}\n{}:\n{}".format(message, label, detail)
