"""Run an isolated Windows consumer profile through the public CLI."""

import hashlib
import importlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest import TestCase, skipUnless

from etchlib.config_validate import validate_repository
from tests.installer_fixtures import FIXTURES, InstallerFixture


class WindowsProfileSchemaTests(TestCase):
    def test_fixture_validates_without_optional_runtime_packages(self) -> None:
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(FIXTURES / "windows-profile", root, dirs_exist_ok=True)
            (root / "defaults.conf").write_text(
                repr(
                    {
                        "schema_version": 1,
                        "plugins": [str(source / "plugins/windows_registry")],
                    }
                ),
                encoding="utf-8",
            )
            shutil.copy2(
                FIXTURES / "installer-ca.pem", root / "modules/workstation/ca.pem"
            )
            validate_repository(root)
            self.assertFalse((root / "managed").exists())


@skipUnless(platform.system() == "Windows", "native Windows consumer profile")
class WindowsProfileTests(InstallerFixture):
    def test_profile_plan_apply_and_idempotence(self) -> None:
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(FIXTURES / "windows-profile", self.root, dirs_exist_ok=True)
        plugin = source / "plugins/windows_registry"
        (self.root / "defaults.conf").write_text(
            repr({"schema_version": 1, "plugins": [str(plugin)]}), encoding="utf-8"
        )
        module = self.root / "modules/workstation"
        shutil.copy2(FIXTURES / "installer-ca.pem", module / "ca.pem")
        self.server.body = (
            b"[IO.File]::WriteAllText((Join-Path $pwd 'installed.txt'), 'ready')\n"
        )
        identity = uuid.uuid4().hex
        config = module / "module.conf"
        config.write_text(
            config.read_text(encoding="utf-8")
            .replace("TEST_ID", identity)
            .replace("https://example.test/installer.ps1", self.url)
            .replace("0" * 64, hashlib.sha256(self.server.body).hexdigest()),
            encoding="utf-8",
        )
        key = r"Software\EtchIntegration-" + identity
        api = importlib.import_module("winreg")

        def cleanup() -> None:
            try:
                api.DeleteKeyEx(api.HKEY_CURRENT_USER, key, api.KEY_WOW64_64KEY)
            except FileNotFoundError:
                pass

        self.addCleanup(cleanup)

        def cli(command: str) -> str:
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    str(source / "etch"),
                    command,
                    "--repo",
                    str(self.root),
                ]
                + ([] if command == "validate" else ["--profile", "windows"]),
                cwd=self.root,
                env=dict(os.environ, PYTHONPATH=""),
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

        cli("validate")
        self.assertIn("windows", cli("facts"))
        self.assertIn("workstation", cli("plan"))
        cli("doctor")
        self.assertEqual(self.server.requests, [])
        self.assertFalse((self.root / "managed").exists())
        self.assertFalse((module / "configured.txt").exists())
        with self.assertRaises(FileNotFoundError):
            api.OpenKey(
                api.HKEY_CURRENT_USER, key, 0, api.KEY_QUERY_VALUE | api.KEY_WOW64_64KEY
            )

        self.assertIn("CHANGED", cli("apply"))
        self.assertEqual(
            (self.root / "managed/settings.conf").read_text(),
            "Etch Windows integration fixture\n",
        )
        self.assertTrue((self.root / "managed/settings.conf").is_symlink())
        self.assertTrue((self.root / "managed/assets").is_symlink())
        self.assertEqual((self.root / "managed/assets").resolve(), module / "assets")
        self.assertEqual((module / "configured.txt").read_text(), "ready")
        self.assertEqual((module / "installed.txt").read_text(), "ready")
        with api.OpenKey(
            api.HKEY_CURRENT_USER, key, 0, api.KEY_QUERY_VALUE | api.KEY_WOW64_64KEY
        ) as handle:
            values: dict[str, tuple[Any, int]] = {
                name: api.QueryValueEx(handle, name) for name in ("enabled", "label")
            }
        self.assertEqual(
            values,
            {"enabled": (1, api.REG_DWORD), "label": ("Etch integration", api.REG_SZ)},
        )
        self.assertEqual(len(self.server.requests), 1)
        self.assertNotIn("CHANGED", cli("apply"))
        self.assertEqual(len(self.server.requests), 1)
