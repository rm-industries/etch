import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.facts.core import core_registry
from etchlib.facts.store import FactStore
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.observations import FactRef, FactResult, FactState
from etchlib.versions.constraints import matches


class VersionProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="version probe ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = Context(self.root, self.root, "tmux", {})
        self.registry = core_registry()

    def probe(self, code: str, **options: Any) -> FactResult:
        return gather_fact(
            self.registry.fact("version"),
            dict(command=[sys.executable, "-S", "-c", code], **options),
            self.context,
        )

    def test_stdout_and_stderr(self) -> None:
        self.assertEqual(self.probe("print('tmux 3.5a')").value, "3.5a")
        self.assertEqual(
            self.probe("import sys; print('OpenSSH_9.8p1', file=sys.stderr)").value,
            "9.8p1",
        )

    def test_argv_and_module_cwd_without_shell(self) -> None:
        marker = self.root / "should-not-exist"
        code = "import os, sys; assert os.getcwd() == sys.argv[1]; assert sys.argv[2].startswith('$(touch '); print('2.1')"
        config = {
            "command": [
                sys.executable,
                "-S",
                "-c",
                code,
                str(self.root.resolve()),
                "$(touch {})".format(marker),
            ]
        }
        result = gather_fact(self.registry.fact("version"), config, self.context)
        self.assertEqual(result.value, "2.1")
        self.assertFalse(marker.exists())

    def test_missing_executable_is_unavailable(self) -> None:
        result = gather_fact(
            self.registry.fact("version"),
            {"command": [str(self.root / "missing"), "-V"]},
            self.context,
        )
        self.assertEqual(result.state, FactState.UNAVAILABLE)

    def test_existing_nonexecutable_is_error(self) -> None:
        path = self.root / "tool"
        path.write_text("print('1.2')")
        result = gather_fact(
            self.registry.fact("version"), {"command": [str(path)]}, self.context
        )
        self.assertEqual(result.state, FactState.ERROR)
        assert result.reason is not None
        self.assertIn("not executable", result.reason)

    def test_relative_executable_and_relative_path_entries(self) -> None:
        (self.root / "python-local").symlink_to(sys.executable)
        with patch.dict(os.environ, {"PATH": "."}):
            for executable in ["./python-local", "python-local"]:
                result = gather_fact(
                    self.registry.fact("version"),
                    {"command": [executable, "-S", "-c", "print('2.1')"]},
                    self.context,
                )
                self.assertEqual(result.value, "2.1", result.reason)

    def test_timeout_exit_invalid_output_and_output_limit(self) -> None:
        for code, options, reason in [
            ("import time; time.sleep(5)", {"timeout": 0.05}, "timed out"),
            ("raise SystemExit(7)", {}, "status 7"),
            ("print('unknown')", {}, "no supported version"),
            ("print('x' * 70000)", {}, "64 KiB"),
        ]:
            with self.subTest(code=code):
                result = self.probe(code, **options)
                self.assertEqual(result.state, FactState.ERROR)
                assert result.reason is not None
                self.assertIn(reason, result.reason)

    def test_invalid_configuration_prevents_execution(self) -> None:
        for config in [
            {"command": "tmux -V"},
            {"command": []},
            {"command": [""]},
            {"command": ["tmux"], "shell": True},
            {"command": ["tmux"], "timeout": True},
            {"command": ["tmux"], "timeout": float("inf")},
            {"command": ["tmux"], "timeout": 0},
        ]:
            with self.subTest(config=config), self.assertRaises(ProviderError):
                gather_fact(self.registry.fact("version"), config, self.context)

    def test_version_fact_integrates_with_cache_and_constraints(self) -> None:
        store = FactStore(self.registry)
        ref = FactRef("tmux", "tmux_version")
        store.declare(
            ref,
            "version",
            {"command": [sys.executable, "-S", "-c", "print('tmux 3.5a')"]},
            self.context,
        )
        result = store.get(ref)
        self.assertEqual(result.state, FactState.VALUE)
        self.assertTrue(matches(result.value, ">=2.1,<4"))
