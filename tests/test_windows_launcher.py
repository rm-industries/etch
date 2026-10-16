"""Windows consumer launchers and their session-specific symlink preflight."""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/minimal"


class SymlinkPreflightTests(unittest.TestCase):
    def probe(self) -> str:
        launcher = EXAMPLE / "etch.ps1"
        self.assertTrue(launcher.is_file(), "the example needs a Windows launcher")
        match = re.search(r"(?ms)^\$symlinkProbe = @'\n(.*?)\n'@", launcher.read_text())
        self.assertIsNotNone(match)
        assert match is not None
        return match.group(1)

    def test_probe_creates_file_and_directory_links_and_cleans_up(self) -> None:
        created = []
        symlink = os.symlink

        def observe(source: str, target: str, *, target_is_directory: bool) -> None:
            created.append((Path(target), target_is_directory))
            symlink(source, target, target_is_directory=target_is_directory)

        with patch("os.symlink", side_effect=observe):
            exec(compile(self.probe(), "symlink preflight", "exec"), {})
        self.assertEqual([directory for _, directory in created], [False, True])
        self.assertTrue(all(not path.parent.exists() for path, _ in created))

    def test_denied_session_reports_developer_mode_without_elevation(self) -> None:
        error = OSError("privilege not held")
        error.winerror = 1314  # type: ignore[attr-defined]
        output = io.StringIO()
        with patch("os.symlink", side_effect=error), contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit) as raised:
                exec(compile(self.probe(), "symlink preflight", "exec"), {})
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Developer Mode", output.getvalue())
        self.assertIn("session", output.getvalue())


@unittest.skipUnless(os.name == "nt", "native Windows consumer launchers")
class WindowsLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="etch launcher ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.consumer = self.root / "consumer repo"
        shutil.copytree(EXAMPLE, self.consumer)
        engine = self.consumer / "vendor/etch/etch"
        engine.parent.mkdir(parents=True)
        engine.write_text(
            "import json, os, sys\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\nsys.exit(7)\n"
        )
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("etch.cmd", "etch.ps1"):
            (self.bin / name).symlink_to(
                os.path.relpath(self.consumer / name, self.bin)
            )
        self.python = str(Path(sys.executable).resolve()).replace("'", "''")

    def invoke(
        self, launcher: Path, *args: str, deny: bool = False
    ) -> subprocess.CompletedProcess[str]:
        deny_probe = (
            "if ($args[1] -eq '-c') { $global:LASTEXITCODE = 1; return }; "
            if deny
            else ""
        )
        command = (
            "function python { "
            + deny_probe
            + "& '"
            + self.python
            + "' @args }; & '"
            + str(launcher).replace("'", "''")
            + "' "
            + " ".join("'" + arg.replace("'", "''") + "'" for arg in args)
        )
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_direct_and_linked_launchers_preserve_checkout_arguments_and_status(
        self,
    ) -> None:
        for launcher in (
            self.consumer / "etch.ps1",
            self.bin / "etch.ps1",
            self.bin / "etch.cmd",
        ):
            result = self.invoke(launcher, "plan", "module with spaces")
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            cwd, args = json.loads(result.stdout)
            self.assertEqual(Path(cwd), self.consumer)
            self.assertEqual(args, ["plan", "module with spaces"])
        default = self.invoke(self.bin / "etch.ps1")
        self.assertEqual(
            json.loads(default.stdout)[1], ["plan", "--profile", "developer"]
        )

    def test_denied_preflight_stops_apply_but_allows_inspection_and_help(self) -> None:
        launcher = self.bin / "etch.ps1"
        self.assertEqual(self.invoke(launcher, "apply", deny=True).returncode, 1)
        for args in (("plan",), ("doctor",), ("apply", "--help")):
            result = self.invoke(launcher, *args, deny=True)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)

    def test_cmd_launcher_runs_from_a_restricted_parent_session(self) -> None:
        command = (
            "Set-ExecutionPolicy -Scope Process Restricted -Force; & '"
            + str(self.bin / "etch.cmd").replace("'", "''")
            + "' plan; exit $LASTEXITCODE"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)[1], ["plan"])
