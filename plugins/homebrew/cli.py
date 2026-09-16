"""Bounded argv-only calls to an explicitly located Homebrew executable."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from etchlib.providers.contracts import Context

from .schema import Target, identifier

OUTPUT_LIMIT = 1024 * 1024


def locate(target: Target, context: Context) -> Optional[str]:
    command = target.command
    if "/" in command or command.startswith("~"):
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
    argv = [executable, *args]
    env = dict(os.environ)
    env.update(
        {
            name: "1"
            for name in (
                "HOMEBREW_NO_AUTO_UPDATE",
                "HOMEBREW_NO_INSTALL_UPGRADE",
                "HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK",
                "HOMEBREW_NO_INSTALL_CLEANUP",
            )
        }
    )
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            completed = subprocess.run(
                argv,
                cwd=context.module_root,
                env=env,
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
            raise ValueError("Homebrew output exceeds 1 MiB per stream")
        if completed.returncode:
            detail = err.decode("utf-8", errors="replace").strip()[:400]
            raise ValueError(
                "Homebrew {} exited with status {}: {}".format(
                    args[0], completed.returncode, detail
                )
            )
        return out.decode("utf-8")
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Homebrew {} timed out".format(args[0])) from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError("Homebrew command failed: {}".format(exc)) from exc


def installed(
    executable: str, target: Target, kind: str, context: Context
) -> tuple[str, ...]:
    output = run(
        executable, target, ("list", "--" + kind, "--full-name", "-1"), context
    )
    return tuple(
        sorted({identifier(line, kind) for line in output.splitlines() if line.strip()})
    )
