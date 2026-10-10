"""Windows installer invocation and local HTTPS execution proof."""

import hashlib
import platform
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from etchlib.providers.contracts import Context
from etchlib.providers.installer.provider import command
from etchlib.providers.installer.schema import normalize
from tests.installer_fixtures import InstallerFixture


class WindowsInstallerSchemaTests(unittest.TestCase):
    def test_powershell_default_and_explicit_unsupported_forms(self) -> None:
        root = Path.cwd()
        context = Context(root, root, "demo", {})
        with patch("platform.system", return_value="Windows"):
            installer = normalize(
                {"url": "https://example.com/install.ps1", "args": ["a b", "$HOME"]},
                context,
            )
            self.assertEqual(installer.shell, "pwsh")
            options = command(installer, root / "installer.ps1")
            self.assertEqual(
                options["argv"][1:],
                (
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(root / "installer.ps1"),
                    "a b",
                    "$HOME",
                ),
            )
            for shell in ("/bin/sh", "cmd.exe", "msiexec.exe"):
                with self.assertRaisesRegex(ValueError, "PowerShell scripts only"):
                    normalize(
                        {"url": "https://example.com/install", "shell": shell}, context
                    )


@unittest.skipUnless(platform.system() == "Windows", "native Windows installers")
class WindowsInstallerTests(InstallerFixture):
    def test_download_execute_and_cleanup_on_both_interpreters(self) -> None:
        self.config.pop("shell")
        self.server.body = b"[IO.File]::WriteAllText((Join-Path $pwd 'download-path'), $PSCommandPath)\n@{arguments=@($args); value=$env:PROFILE; cwd=$pwd.Path} | ConvertTo-Json | Set-Content -Encoding utf8 installed\n"
        import json
        import shutil

        original = shutil.which
        for fallback in (False, True):

            def discover(
                name: str, path: str, fallback: bool = fallback
            ) -> Optional[str]:
                return (
                    None if fallback and name == "pwsh" else original(name, path=path)
                )

            with patch(
                "etchlib.providers.commands.windows.shutil.which", side_effect=discover
            ):
                args = ["two words", "$HOME; literal", 'a"b', ""]
                plan = self.plan(
                    args=args,
                    env={"PROFILE": "literal $HOME"},
                    sha256=hashlib.sha256(self.server.body).hexdigest(),
                )
                self.assertTrue(self.apply(plan).changed)
                result = json.loads(
                    (self.root / "installed").read_text(encoding="utf-8-sig")
                )
                self.assertEqual(
                    result,
                    {
                        "arguments": args,
                        "value": "literal $HOME",
                        "cwd": str(self.root),
                    },
                )
                self.assertFalse(
                    Path((self.root / "download-path").read_text()).exists()
                )
                self.assertFalse(self.apply(plan).changed)
                (self.root / "installed").unlink()
        self.assertEqual(len(self.server.requests), 2)

    def test_execution_failure_and_hash_failure_never_leave_downloads(self) -> None:
        self.config.pop("shell")
        self.server.body = b"[IO.File]::WriteAllText((Join-Path $pwd 'download-path'), $PSCommandPath)\nexit 7\n"
        with self.assertRaisesRegex(ValueError, "status 7"):
            self.apply(self.plan())
        self.assertFalse(Path((self.root / "download-path").read_text()).exists())
        (self.root / "download-path").unlink()
        with self.assertRaisesRegex(ValueError, "SHA-256|sha256|hash"):
            self.apply(self.plan(sha256="0" * 64))
        self.assertFalse((self.root / "download-path").exists())
