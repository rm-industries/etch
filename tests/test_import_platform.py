"""Import isolation and timeout cleanup use the native platform contract."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.importing.git import Git
from etchlib.importing.source import relative


class ImportPlatformTests(unittest.TestCase):
    def test_windows_environment_preserves_only_required_system_settings(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("platform.system", return_value="Windows"),
            patch.dict(os.environ, SystemRoot="C:/Windows", GIT_CONFIG_COUNT="99"),
            patch.object(Git, "run", return_value=b"git version 2.50.0"),
        ):
            root = Path(temporary)
            git = Git(root)
            self.assertEqual(git.env["SystemRoot"], "C:/Windows")
            self.assertEqual(git.env["USERPROFILE"], str(root))
            self.assertEqual(git.env["GIT_ASKPASS"], "")
            self.assertEqual(git.env["GIT_TERMINAL_PROMPT"], "0")
            self.assertNotIn("GIT_CONFIG_COUNT", git.env)
            self.assertEqual(list((root / "disabled-hooks").iterdir()), [])

    def test_windows_timeout_terminates_process_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            git = Git(Path(temporary))
            with (
                patch("platform.system", return_value="Windows"),
                patch.dict(os.environ, SystemRoot="C:/Windows"),
                patch("etchlib.importing.git.subprocess.Popen") as popen,
                patch("etchlib.importing.git.subprocess.run") as terminate,
                patch("etchlib.importing.git.os.killpg", create=True) as kill_group,
            ):
                process = popen.return_value.__enter__.return_value
                process.pid = 1234
                terminate.return_value.returncode = 0
                process.communicate.side_effect = subprocess.TimeoutExpired("git", 1)
                with self.assertRaisesRegex(ValueError, "120 seconds"):
                    git.run("fetch")
                kill_group.assert_not_called()
                argv = terminate.call_args.args[0]
                self.assertEqual(
                    Path(argv[0]), Path("C:/Windows/System32/taskkill.exe")
                )
                self.assertEqual(argv[1:], ["/F", "/T", "/PID", "1234"])
                self.assertFalse(popen.call_args.kwargs["start_new_session"])
                self.assertEqual(terminate.call_args.kwargs["timeout"], 10)
                process.wait.assert_called_once()

    def test_windows_cleanup_failure_still_kills_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            git = Git(Path(temporary))
            with (
                patch("platform.system", return_value="Windows"),
                patch.dict(os.environ, SystemRoot="C:/Windows"),
                patch("etchlib.importing.git.subprocess.Popen") as popen,
                patch(
                    "etchlib.importing.git.subprocess.run",
                    side_effect=subprocess.TimeoutExpired("taskkill", 10),
                ),
            ):
                process = popen.return_value.__enter__.return_value
                process.poll.return_value = None
                process.communicate.side_effect = subprocess.TimeoutExpired("git", 1)
                with self.assertRaisesRegex(ValueError, "120 seconds"):
                    git.run("fetch")
                process.kill.assert_called_once()

    def test_native_timeout_reaps_the_child_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            git = Git(Path(temporary))
            original = subprocess.Popen
            children: list[subprocess.Popen[bytes]] = []

            def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
                if argv[0] == git.executable:
                    argv = [sys.executable, "-S", "-c", "import time; time.sleep(60)"]
                    child = original(argv, **kwargs)
                    children.append(child)
                    return child
                return original(argv, **kwargs)

            with patch("etchlib.importing.git.subprocess.Popen", side_effect=launch):
                git.deadline = time.monotonic() + 0.2
                with self.assertRaisesRegex(ValueError, "120 seconds"):
                    git.run("--version")
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())

    def test_windows_paths_are_rejected_before_materialization(self) -> None:
        for path in (
            "C:/outside",
            "files/asset:stream",
            "files/NUL.txt",
            "files/CON",
            "files/CONIN$",
            "files/CONOUT$",
            "files/com1",
            "files/LPT9.log",
            "files/COM¹.txt",
            "files/trailing.",
            "files/trailing ",
            'files/bad"name',
            "files/a?b",
            "files/a*b",
            "files/a<b",
            "files/a>b",
            "files/a|b",
        ):
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(ValueError, "unsafe import path"),
            ):
                relative(path)
        self.assertEqual(relative("files/console.txt"), ("files", "console.txt"))
