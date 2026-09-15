"""Gather a version from a bounded-duration argv command, never through a shell."""

import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from etchlib.providers.observations import FactResult, FactState
from etchlib.versions.parser import extract_version

OUTPUT_LIMIT = 65536


class VersionProbe:
    name = "version"

    def validate(self, config, context):
        if not isinstance(config, dict) or set(config) - {"command", "timeout"}:
            raise ValueError("version expects command and optional timeout")
        argv = config.get("command")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(v, str) or "\x00" in v for v in argv)
            or not argv[0]
        ):
            raise ValueError("version command must be a nonempty argv list")
        timeout = config.get("timeout", 10)
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError(
                "version timeout must be a positive finite number of seconds"
            )

    def gather(self, config, context):
        argv = list(config["command"])
        try:
            executable = argv[0]
            if "/" in executable:
                path = Path(executable).expanduser()
                executable = str(
                    path if path.is_absolute() else context.module_root / path
                )
            # Resolve relative PATH entries against the same cwd used by the child.
            search = os.pathsep.join(
                str(context.module_root / p) if not os.path.isabs(p) else p
                for p in os.get_exec_path()
            )
            found = shutil.which(executable, path=search)
            if found is None:
                candidates = (
                    [Path(executable)]
                    if "/" in executable
                    else [Path(p) / executable for p in search.split(os.pathsep)]
                )
                if any(p.exists() for p in candidates):
                    return FactResult(
                        FactState.ERROR,
                        reason="command {!r} exists but is not executable".format(
                            argv[0]
                        ),
                    )
                return FactResult(
                    FactState.UNAVAILABLE,
                    reason="command {!r} not found".format(argv[0]),
                )
            argv[0] = os.path.abspath(found)
            # Spool output to files: noisy commands cannot fill memory while running.
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                completed = subprocess.run(
                    argv,
                    cwd=context.module_root,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=config.get("timeout", 10),
                    shell=False,
                )
                if completed.returncode:
                    return FactResult(
                        FactState.ERROR,
                        reason="version command exited with status {}".format(
                            completed.returncode
                        ),
                    )
                stdout.seek(0)
                stderr.seek(0)
                out, err = stdout.read(OUTPUT_LIMIT + 1), stderr.read(OUTPUT_LIMIT + 1)
            if len(out) > OUTPUT_LIMIT or len(err) > OUTPUT_LIMIT:
                return FactResult(
                    FactState.ERROR, reason="version output exceeds 64 KiB per stream"
                )
            output = out if out.strip() else err
            return FactResult(FactState.VALUE, extract_version(output.decode("utf-8")))
        except subprocess.TimeoutExpired:
            return FactResult(FactState.ERROR, reason="version command timed out")
        except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
            return FactResult(
                FactState.ERROR, reason="version probe failed: {}".format(exc)
            )
