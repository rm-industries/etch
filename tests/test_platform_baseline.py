"""Portable checkout startup, facts and planning; no optional dependencies."""

import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.diagnostics.doctor import diagnose
from etchlib.facts.platform import PlatformProbe
from etchlib.facts.probes import LocalProbe
from etchlib.providers.commands.runtime import checked
from etchlib.providers.contracts import Context


class PlatformBaselineTests(unittest.TestCase):
    def test_windows_platform_facts(self) -> None:
        context = Context(Path.cwd(), Path.cwd(), "demo", {})
        with (
            patch("platform.system", return_value="Windows"),
            patch("platform.machine", return_value="AMD64"),
        ):
            self.assertEqual(PlatformProbe("os").gather({}, context).value, "windows")
            self.assertEqual(PlatformProbe("arch").gather({}, context).value, "x86_64")
            self.assertIsNone(PlatformProbe("distro").gather({}, context).value)

    def test_clean_checkout_loads_facts_conditions_plan_and_doctor(self) -> None:
        engine = Path(__file__).resolve().parents[1] / "etch"
        with tempfile.TemporaryDirectory(prefix="etch baseline ") as temp:
            root = Path(temp)
            module = root / "modules" / "demo"
            module.mkdir(parents=True)
            (root / "profiles").mkdir()
            (root / "profiles" / "baseline.conf").write_text(
                repr({"schema_version": 1, "name": "baseline", "modules": ["demo"]}),
                encoding="utf-8",
            )
            system = {"darwin": "macos"}.get(
                platform.system().lower(), platform.system().lower()
            )
            (module / "module.conf").write_text(
                repr(
                    {
                        "schema_version": 1,
                        "name": "demo",
                        "when": {"os": system},
                        "facts": {
                            "python": {
                                "provider": "command_path",
                                "config": sys.executable,
                            }
                        },
                        "actions": [],
                    }
                ),
                encoding="utf-8",
            )
            diagnosis = diagnose(
                load_repository(root, profile="baseline"), core_registry()
            )
            self.assertEqual(diagnosis.errors, ())
            self.assertIsNotNone(diagnosis.plan)
            for command in ("validate", "facts", "plan", "doctor"):
                result = subprocess.run(
                    [sys.executable, "-S", str(engine), command, "--repo", str(root)]
                    + ([] if command == "validate" else ["--profile", "baseline"]),
                    cwd=root,
                    env=dict(os.environ, PYTHONPATH=""),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((root / ".etch").exists())

    @unittest.skipUnless(os.name == "nt", "Windows executable discovery")
    def test_windows_relative_executable_and_suffix_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bin").mkdir()
            (root / "bin" / "tool.exe").touch()
            context = Context(root, root, "demo", {})
            with patch.dict(os.environ, PATHEXT=".EXE", PATH=str(root / "bin")):
                # Python 3.9 needs an explicit suffix for commands with a directory.
                for command in ("tool", r"bin\tool.exe", "bin/tool.exe"):
                    self.assertTrue(
                        LocalProbe("command").gather(command, context).value
                    )
                    self.assertTrue(checked({"check": {"command": command}}, context))
