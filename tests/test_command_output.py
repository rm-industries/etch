"""Child output is quiet on success, diagnostic on failure and live on request."""

import subprocess
import sys
import unittest
from pathlib import Path


class CommandOutputTests(unittest.TestCase):
    def invoke(
        self,
        code: str,
        *,
        verbose: bool = False,
        quiet: bool = False,
        timeout: float = 5,
    ) -> subprocess.CompletedProcess[str]:
        source = """from pathlib import Path
import sys
from etchlib.providers.contracts import Context
from etchlib.providers.commands.runtime import run
context = Context(Path.cwd(), Path.cwd(), 'demo', {}, verbose=%r)
try:
    run({'provider': 'shell', 'argv': [sys.executable, '-c', %r], 'quiet': %r, 'timeout': %r}, context)
except ValueError as error:
    print(error, file=sys.stderr)
    raise SystemExit(1)
""" % (verbose, code, quiet, timeout)
        return subprocess.run(
            [sys.executable, "-S", "-c", source],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_success_is_quiet_and_verbose_is_live(self) -> None:
        for verbose, quiet, expected in (
            (False, False, ""),
            (True, False, "vendor banner\n"),
            (True, True, ""),
        ):
            result = self.invoke("print('vendor banner')", verbose=verbose, quiet=quiet)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected)

    def test_failure_and_timeout_include_captured_output(self) -> None:
        failed = self.invoke(
            "import sys; print('useful stdout'); print('useful stderr', file=sys.stderr); sys.exit(7)",
            quiet=True,
        )
        self.assertEqual(failed.returncode, 1)
        self.assertIn("status 7", failed.stderr)
        self.assertIn("useful stdout", failed.stderr)
        self.assertIn("useful stderr", failed.stderr)
        timed = self.invoke(
            "import time; print('before timeout', flush=True); time.sleep(10)",
            timeout=1,
        )
        self.assertIn("command timed out", timed.stderr)
        self.assertIn("before timeout", timed.stderr)

    def test_failure_diagnostics_are_bounded(self) -> None:
        result = self.invoke(
            "import sys; print('x' * 100000); print('last detail'); sys.exit(1)"
        )
        self.assertLess(len(result.stderr), 17000)
        self.assertIn("last detail", result.stderr)
