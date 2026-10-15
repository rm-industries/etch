"""Bounded argv execution of native Codex commands, independent of core loading."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from etchlib.providers.contracts import Context

from .schema import Target

OUTPUT_LIMIT = 1024 * 1024


def locate(target: Target, context: Context) -> Optional[str]:
    command = target.command
    if "/" in command or "\\" in command or command.startswith("~"):
        path = Path(command).expanduser()
        command = str(path if path.is_absolute() else context.module_root / path)
    search = os.pathsep.join(
        str(context.module_root / entry) if not os.path.isabs(entry) else entry
        for entry in os.get_exec_path()
    )
    found = shutil.which(command, path=search)
    return os.path.abspath(found) if found else None


def run(
    executable: str, target: Target, args: tuple[str, ...], context: Context
) -> str:
    if os.name == "nt" and os.path.splitext(executable)[1].lower() in (".bat", ".cmd"):
        raise ValueError(
            "Codex batch wrappers are unsupported; select the native codex.exe"
        )
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            result = subprocess.run(
                [executable, *args],
                cwd=context.module_root,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=target.timeout,
                shell=False,
            )
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(OUTPUT_LIMIT + 1), stderr.read(OUTPUT_LIMIT + 1)
        if len(out) > OUTPUT_LIMIT or len(err) > OUTPUT_LIMIT:
            raise ValueError("Codex output exceeds 1 MiB per stream")
        if result.returncode:
            detail = (
                err.decode("utf-8", errors="replace").strip()
                or out.decode("utf-8", errors="replace").strip()
            )[:400]
            raise ValueError(
                "Codex {} exited with status {}: {}".format(
                    " ".join(args[:3]), result.returncode, detail
                )
            )
        return out.decode("utf-8")
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Codex command timed out") from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError("Codex command failed: {}".format(exc)) from exc


def document(
    executable: str, target: Target, args: tuple[str, ...], context: Context
) -> dict[str, Any]:
    try:
        value = json.loads(run(executable, target, args + ("--json",), context))
    except json.JSONDecodeError as exc:
        raise ValueError("Codex returned invalid JSON inventory/result") from exc
    if not isinstance(value, dict):
        raise ValueError("Codex JSON inventory/result must be an object")
    return value
