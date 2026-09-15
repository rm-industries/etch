import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.facts.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.observations import FactResult, FactState


class ProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.context = Context(self.root, self.root, "example", {})
        self.registry = core_registry()

    def gather(self, name: str, config: Any) -> FactResult:
        return gather_fact(self.registry.fact(name), config, self.context)

    def test_commands_are_inspected_not_executed(self) -> None:
        command = self.root / "example"
        command.write_text("#!/bin/sh\nexit 99\n")
        command.chmod(0o755)
        with patch.dict(os.environ, {"PATH": str(self.root)}):
            self.assertIs(self.gather("command", "example").value, True)
            self.assertEqual(self.gather("command_path", "example").value, str(command))
            result = self.gather("command", "missing")
            self.assertEqual(result.state, FactState.UNAVAILABLE)
            assert result.reason is not None
            self.assertIn("not found", result.reason)
        self.assertEqual(self.gather("command_path", "./example").value, str(command))

    def test_environment_distinguishes_empty_from_absent(self) -> None:
        with patch.dict(os.environ, {"PRESENT": ""}, clear=True):
            self.assertEqual(self.gather("env", "PRESENT").value, "")
            self.assertEqual(self.gather("env", "MISSING").state, FactState.UNAVAILABLE)

    def test_file_directory_missing_and_broken_symlink(self) -> None:
        (self.root / "file").write_text("hello")
        (self.root / "directory").mkdir()
        (self.root / "broken").symlink_to(self.root / "missing")
        for name, config, value in [
            ("file_exists", "file", True),
            ("directory_exists", "file", False),
            ("directory_exists", "directory", True),
            ("path_exists", "missing", False),
            ("path_exists", "broken", False),
        ]:
            with self.subTest(name=name, config=config):
                result = self.gather(name, config)
                self.assertEqual(result.state, FactState.VALUE)
                self.assertIs(result.value, value)

    def test_permission_errors_are_not_absence(self) -> None:
        with patch.object(Path, "stat", side_effect=PermissionError("denied")):
            result = self.gather("path_exists", "file")
        self.assertEqual(result.state, FactState.ERROR)
        assert result.reason is not None
        self.assertIn("denied", result.reason)

    def test_platform_normalization(self) -> None:
        with (
            patch("etchlib.facts.platform.platform.system", return_value="Darwin"),
            patch("etchlib.facts.platform.platform.machine", return_value="arm64"),
        ):
            self.assertEqual(self.gather("os", {}).value, "macos")
            self.assertEqual(self.gather("arch", {}).value, "aarch64")
            self.assertEqual(self.gather("distro", {}).state, FactState.UNAVAILABLE)

    def test_linux_distribution_without_command_execution(self) -> None:
        with (
            patch("etchlib.facts.platform.platform.system", return_value="Linux"),
            patch.object(
                Path, "read_text", return_value='NAME="Example Linux"\nID="ubuntu"\n'
            ),
        ):
            self.assertEqual(self.gather("distro", {}).value, "ubuntu")

    def test_distribution_missing_malformed_and_unreadable(self) -> None:
        with patch("etchlib.facts.platform.platform.system", return_value="Linux"):
            with patch.object(Path, "read_text", side_effect=FileNotFoundError):
                self.assertEqual(self.gather("distro", {}).state, FactState.UNAVAILABLE)
            with patch.object(Path, "read_text", return_value='ID="unterminated'):
                self.assertEqual(self.gather("distro", {}).state, FactState.ERROR)
            with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
                self.assertEqual(self.gather("distro", {}).state, FactState.ERROR)
