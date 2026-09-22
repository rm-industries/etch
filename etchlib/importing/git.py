"""Bounded Git plumbing in an isolated repository, without checkout or hooks."""

import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import BinaryIO, Optional

from .source import Source

DIAGNOSTIC_LIMIT = 1024 * 1024


class Git:
    def __init__(self, root: Path) -> None:
        executable = shutil.which("git")
        if executable is None:
            raise ValueError(
                "import requires Git 2.25 or newer; install Git explicitly"
            )
        self.executable = str(Path(executable).resolve())
        self.root = root
        self.deadline = time.monotonic() + 120
        # Do not inherit Git, proxy, TLS, credential or subprocess configuration.
        self.env = {
            "PATH": os.defpath,
            "HOME": str(root),
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/usr/bin/false",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_ALLOW_PROTOCOL": "https",
        }
        version = self.run("--version")
        match = re.search(rb"git version (\d+)\.(\d+)", version)
        if match is None or (int(match[1]), int(match[2])) < (2, 25):
            raise ValueError("import requires Git 2.25 or newer")
        self.run("init", "--bare", "--template=", str(root))

    def run(
        self,
        *args: str,
        input_data: Optional[bytes] = None,
        output: Optional[BinaryIO] = None,
    ) -> bytes:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Git acquisition exceeded 120 seconds")
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                with subprocess.Popen(
                    [
                        self.executable,
                        "-c",
                        "credential.helper=",
                        "-c",
                        "core.hooksPath=/dev/null",
                        "-c",
                        "http.followRedirects=false",
                        "-c",
                        "http.sslVerify=true",
                        *args,
                    ],
                    cwd=self.root,
                    env=self.env,
                    stdin=subprocess.PIPE,
                    stdout=output if output is not None else stdout,
                    stderr=stderr,
                    start_new_session=True,
                ) as process:
                    try:
                        process.communicate(
                            input=input_data if input_data is not None else b"",
                            timeout=remaining,
                        )
                    except subprocess.TimeoutExpired:
                        # Git HTTPS helpers belong to the same fresh process group.
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        raise
                    returncode = process.returncode
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Git acquisition exceeded 120 seconds") from exc
            stderr.seek(0)
            detail = stderr.read(DIAGNOSTIC_LIMIT + 1)
            if len(detail) > DIAGNOSTIC_LIMIT:
                raise ValueError("Git diagnostic output exceeded 1 MiB")
            if returncode:
                # Remote diagnostics may include arbitrary content; never echo them.
                raise ValueError(
                    "Git {} failed (exit {}); check the public source, ref, TLS and network".format(
                        args[0], returncode
                    )
                )
            if (
                b"filtering not recognized" in detail
                or b"does not support filter" in detail
            ):
                self.filter_fallback = True
            stdout.seek(0)
            data = stdout.read(DIAGNOSTIC_LIMIT + 1)
            if len(data) > DIAGNOSTIC_LIMIT:
                raise ValueError("Git metadata output exceeded 1 MiB")
            return data

    filter_fallback = False

    def fetch(self, source: Source) -> str:
        self.run("config", "remote.origin.url", source.url)
        self.run("config", "remote.origin.promisor", "true")
        self.run("config", "remote.origin.partialclonefilter", "blob:none")
        self.run(
            "fetch",
            "--depth=1",
            "--no-tags",
            "--no-recurse-submodules",
            "--filter=blob:none",
            "origin",
            source.ref,
        )
        commit = (
            self.run("rev-parse", "--verify", "FETCH_HEAD^{commit}")
            .decode("ascii")
            .strip()
        )
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("import supports SHA-1 Git repositories only")
        if (
            re.fullmatch(r"[0-9a-fA-F]{40}", source.ref)
            and commit != source.ref.lower()
        ):
            raise ValueError("fetched commit does not match requested commit")
        return commit
