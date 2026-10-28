"""Small argv-only native command support for independently loaded providers."""

import os
import shutil
import subprocess
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import IO, Mapping, Optional

OUTPUT_LIMIT = 1024 * 1024


def locate(
    command: str, cwd: Path, env: Optional[Mapping[str, str]] = None
) -> Optional[str]:
    if "/" in command or "\\" in command or command.startswith("~"):
        path = Path(command).expanduser()
        command = str(path if path.is_absolute() else cwd / path)
    search = os.pathsep.join(
        str(cwd / entry) if not os.path.isabs(entry) else entry
        for entry in os.get_exec_path(env)
    )
    found = shutil.which(command, path=search)
    return os.path.abspath(found) if found else None


def run(
    executable: str,
    args: tuple[str, ...],
    *,
    cwd: Path,
    timeout: float,
    label: str,
    env: Optional[Mapping[str, str]] = None,
) -> str:
    if os.name == "nt" and os.path.splitext(executable)[1].lower() in (".bat", ".cmd"):
        raise ValueError(
            label + " batch wrappers are unsupported; select a native executable"
        )
    output, errors = bytearray(), bytearray()
    interrupted, stopped = Event(), Event()
    read_errors: list[str] = []

    def capture(stream: IO[bytes], buffer: bytearray) -> None:
        try:
            while not stopped.is_set():
                chunk = stream.read(min(65536, OUTPUT_LIMIT + 1 - len(buffer)))
                if not chunk:
                    return
                buffer.extend(chunk)
                if len(buffer) > OUTPUT_LIMIT:
                    interrupted.set()
                    return
        except (OSError, ValueError) as exc:
            if not stopped.is_set():
                read_errors.append(str(exc))
                interrupted.set()

    try:
        with subprocess.Popen(
            [executable, *args],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            shell=False,
        ) as process:
            assert process.stdout is not None and process.stderr is not None
            readers = [
                Thread(target=capture, args=(stream, buffer), daemon=True)
                for stream, buffer in (
                    (process.stdout, output),
                    (process.stderr, errors),
                )
            ]
            deadline = monotonic() + timeout
            for reader in readers:
                reader.start()
            try:
                while process.poll() is None:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(executable, timeout)
                    if interrupted.wait(min(0.01, remaining)):
                        break
                if interrupted.is_set() and process.poll() is None:
                    process.kill()
                    process.wait()
                for reader in readers:
                    reader.join(max(0, deadline - monotonic()))
                if any(reader.is_alive() for reader in readers):
                    raise subprocess.TimeoutExpired(executable, timeout)
            finally:
                stopped.set()
                if process.poll() is None:
                    process.kill()
                process.wait()
        if len(output) > OUTPUT_LIMIT or len(errors) > OUTPUT_LIMIT:
            raise ValueError(
                label + " output exceeds {} bytes per stream".format(OUTPUT_LIMIT)
            )
        if read_errors:
            raise ValueError(label + " command output failed: " + read_errors[0])
        if process.returncode:
            detail = (
                errors.decode("utf-8", errors="replace").strip()
                or output.decode("utf-8", errors="replace").strip()
            )[:400]
            raise ValueError(
                "{} command exited with status {}: {}".format(
                    label, process.returncode, detail
                )
            )
        return output.decode("utf-8")
    except subprocess.TimeoutExpired as exc:
        raise ValueError(label + " command timed out") from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError("{} command failed: {}".format(label, exc)) from exc
