"""Windows invocation rules and native PowerShell integration."""

import json
import platform
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers.commands.schema import normalize
from etchlib.providers.commands.windows import invocation
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import PlanStatus


class WindowsCommandTests(unittest.TestCase):
    def test_invocation_keeps_literal_script_arguments(self) -> None:
        root = Path.cwd()
        context = Context(root, root, "demo", {})
        script = root / "example.ps1"
        args = ["a b", "$HOME; echo bad", 'a"b', ""]
        options = {"provider": "script", "argv": (str(script), *args)}
        with patch(
            "etchlib.providers.commands.windows.shutil.which",
            return_value=str(root / "pwsh.exe"),
        ):
            argv = invocation(options, context, {})
        self.assertEqual(
            argv[1:], ["-NoProfile", "-NonInteractive", "-File", str(script), *args]
        )
        with patch(
            "etchlib.providers.commands.windows.shutil.which", return_value=None
        ):
            with self.assertRaisesRegex(ValueError, "PowerShell requires"):
                invocation(options, context, {})
        with self.assertRaisesRegex(ValueError, "sudo"):
            invocation(dict(options, sudo=True), context, {})
        with patch(
            "etchlib.providers.commands.windows.shutil.which",
            return_value="example.cmd",
        ):
            with self.assertRaisesRegex(ValueError, "batch files"):
                invocation({"provider": "shell", "argv": ("example.cmd",)}, context, {})

    def test_powershell_fallback_preserves_arguments(self) -> None:
        root = Path.cwd()
        context = Context(root, root, "demo", {})
        for options in (
            {"provider": "script", "argv": (str(root / "example.ps1"), "a b", "$HOME")},
            {
                "provider": "shell",
                "command": "Write-Output 'hello'",
                "argv": (
                    "pwsh",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Write-Output 'hello'",
                ),
            },
        ):
            with patch(
                "etchlib.providers.commands.windows.shutil.which",
                side_effect=[None, str(root / "powershell.exe")],
            ) as discovery:
                argv = invocation(options, context, {})
            self.assertEqual(argv[0], str(root / "powershell.exe"))
            self.assertEqual(discovery.call_args.args[0], "powershell.exe")

    def test_windows_string_shell_uses_powershell(self) -> None:
        root = Path.cwd()
        context = Context(root, root, "demo", {})
        with patch("platform.system", return_value="Windows"):
            options = normalize("shell", {"command": "Write-Output 'hello'"}, context)[
                0
            ]
        self.assertEqual(
            options["argv"],
            (
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Write-Output 'hello'",
            ),
        )

    @unittest.skipUnless(platform.system() == "Windows", "native PowerShell execution")
    def test_powershell_arguments_environment_cwd_checks_and_exit_status(self) -> None:
        self.exercise_powershell(False)
        self.exercise_powershell(True)

    def exercise_powershell(self, fallback: bool) -> None:
        import shutil

        original = shutil.which

        def discover(command: str, path: str) -> Optional[str]:
            if fallback and command == "pwsh":
                return None
            return original(command, path=path)

        with (
            patch(
                "etchlib.providers.commands.windows.shutil.which", side_effect=discover
            ),
            tempfile.TemporaryDirectory(prefix="etch PowerShell ") as temp,
        ):
            root = Path(temp).resolve()
            context = Context(root, root, "demo", {})
            script = root / "script with spaces.ps1"
            script.write_text(
                "@{ arguments = @($args); cwd = (Get-Location).Path; value = $env:ETCH_TEST; module = $env:ETCH_MODULE } | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 result.json\n",
                encoding="utf-8",
            )
            args = ["two words", "$HOME; echo bad", 'a"b', ""]
            config = {
                "path": script.name,
                "args": args,
                "env": {"ETCH_TEST": "literal $HOME; value"},
                "check": {"file_exists": "result.json"},
            }
            provider = core_registry().action("script")
            plan = plan_action(provider, config, context)
            self.assertFalse((root / "result.json").exists())
            self.assertTrue(provider.provider.apply(plan, context).changed)
            result = json.loads((root / "result.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(
                result,
                {
                    "arguments": args,
                    "cwd": str(root),
                    "value": "literal $HOME; value",
                    "module": "demo",
                },
            )
            self.assertEqual(
                plan_action(provider, config, context).status, PlanStatus.SKIP
            )
            script.write_text("exit 7\n", encoding="utf-8")
            plan = plan_action(provider, {"path": script.name}, context)
            with self.assertRaisesRegex(ValueError, "status 7"):
                provider.provider.apply(plan, context)
            shell = core_registry().action("shell")
            plan = plan_action(
                shell, {"command": "Set-Content shell-result.txt 'done'"}, context
            )
            self.assertTrue(shell.provider.apply(plan, context).changed)
            self.assertTrue((root / "shell-result.txt").exists())
