"""Native provider commands preserve argv and bound captured child output."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.providers import native


class NativeCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def run_python(self, code: str, *args: str, timeout: float = 5) -> str:
        return native.run(
            sys.executable,
            ("-c", code, *args),
            cwd=self.root,
            timeout=timeout,
            label="Test tool",
        )

    def test_literal_arguments_closed_stdin_cwd_and_child_environment(self) -> None:
        env = dict(os.environ, ETCH_NATIVE_TEST="child")
        output = native.run(
            sys.executable,
            (
                "-c",
                "import json,os,sys; print(json.dumps([sys.argv[1:], os.getcwd(), "
                "os.environ['ETCH_NATIVE_TEST'], sys.stdin.read()]))",
                "space name",
                "$(touch escaped)",
                ";exit 1",
            ),
            cwd=self.root,
            timeout=5,
            label="Test tool",
            env=env,
        )
        self.assertEqual(
            json.loads(output),
            [
                ["space name", "$(touch escaped)", ";exit 1"],
                str(self.root),
                "child",
                "",
            ],
        )
        self.assertNotEqual(os.environ.get("ETCH_NATIVE_TEST"), "child")
        self.assertFalse((self.root / "escaped").exists())

    def test_lookup_anchors_relative_commands_and_path_at_child_cwd(self) -> None:
        directory = self.root / "tools with spaces"
        directory.mkdir()
        tool = directory / "native-tool"
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
        env = dict(os.environ, PATH="tools with spaces")
        self.assertEqual(native.locate("native-tool", self.root, env), str(tool))
        self.assertEqual(
            native.locate("tools with spaces/native-tool", self.root), str(tool)
        )
        self.assertIsNone(native.locate("absent-native-command", self.root, env))

    def test_nonzero_exit_reports_status_and_stderr_or_stdout(self) -> None:
        for stream in ("sys.stderr", "sys.stdout"):
            with (
                self.subTest(stream=stream),
                self.assertRaisesRegex(
                    ValueError, "Test tool.*status 7.*controlled failure"
                ),
            ):
                self.run_python(
                    "import sys; print('controlled failure', file="
                    + stream
                    + "); sys.exit(7)"
                )

    def test_timeout_output_limit_and_invalid_encoding_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Test tool.*timed out"):
            self.run_python("import time; time.sleep(2)", timeout=0.02)
        for stream in ("sys.stdout", "sys.stderr"):
            with self.subTest(stream=stream), patch.object(native, "OUTPUT_LIMIT", 32):
                with self.assertRaisesRegex(ValueError, "output exceeds"):
                    self.run_python("import sys; " + stream + ".write('x' * 33)")
        with self.assertRaisesRegex(ValueError, "Test tool.*failed"):
            self.run_python("import sys; sys.stdout.buffer.write(b'\\xff')")

    def test_output_overflow_stops_before_child_finishes(self) -> None:
        marker = self.root / "completed"
        with patch.object(native, "OUTPUT_LIMIT", 32):
            with self.assertRaisesRegex(ValueError, "output exceeds"):
                self.run_python(
                    "import sys,time; from pathlib import Path; "
                    "sys.stdout.write('x' * 33); sys.stdout.flush(); "
                    "time.sleep(0.5); Path(sys.argv[1]).touch()",
                    str(marker),
                )
        self.assertFalse(marker.exists())

    def test_missing_executable_is_actionable(self) -> None:
        with self.assertRaisesRegex(ValueError, "Test tool.*failed"):
            native.run(
                "/absent/native-command",
                (),
                cwd=self.root,
                timeout=1,
                label="Test tool",
            )

    def test_windows_batch_files_never_execute(self) -> None:
        marker = self.root / "should-not-exist"
        wrapper = self.root / "tool.cmd"
        wrapper.write_text("touch " + str(marker))
        wrapper.chmod(0o755)
        with patch("os.name", "nt"):
            with self.assertRaisesRegex(ValueError, "batch wrappers"):
                native.run(
                    str(wrapper), (), cwd=self.root, timeout=1, label="Test tool"
                )
        self.assertFalse(marker.exists())
