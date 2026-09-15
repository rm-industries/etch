import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import PlanStatus


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.context = Context(self.root, self.root, "example", {})
        self.registry = core_registry()

    def plan(self, config, name="shell"):
        return plan_action(self.registry.action(name), config, self.context)

    def apply(self, plan, name="shell"):
        return self.registry.action(name).provider.apply(plan, self.context)

    def test_plan_is_honest_and_does_not_run(self):
        config = {"command": "touch marker", "description": "Create marker"}
        plan = self.plan(config)
        self.assertEqual(plan.status, PlanStatus.RUN)
        self.assertTrue(plan.opaque)
        self.assertFalse((self.root / "marker").exists())
        self.assertTrue(self.apply(plan).changed)
        self.assertTrue((self.root / "marker").exists())

    def test_argv_is_not_shell_evaluated(self):
        command = [
            sys.executable,
            "-S",
            "-c",
            "import sys; assert sys.argv[1] == '$(touch marker)'",
            "$(touch marker)",
        ]
        self.apply(self.plan({"command": command}))
        self.assertFalse((self.root / "marker").exists())

    def test_environment_metadata_overrides_and_cwd(self):
        code = "import json,os; open('result.json','w').write(json.dumps(dict(os.environ,cwd=os.getcwd())))"
        with patch.dict(os.environ, {"INHERITED": "yes"}):
            self.apply(
                self.plan(
                    {
                        "command": [sys.executable, "-S", "-c", code],
                        "env": {"CUSTOM": "value", "ETCH_MODULE": "cannot override"},
                    }
                )
            )
        result = json.loads((self.root / "result.json").read_text())
        self.assertEqual(result["cwd"], str(self.root))
        self.assertEqual(result["CUSTOM"], "value")
        self.assertEqual(result["INHERITED"], "yes")
        self.assertEqual(result["ETCH_MODULE"], "example")
        self.assertTrue(result["ETCH_OS"])

    def test_check_skips_and_second_run_is_noop(self):
        config = {"command": "touch marker", "check": {"file_exists": "marker"}}
        plan = self.plan(config)
        self.assertTrue(self.apply(plan).changed)
        self.assertFalse(self.apply(plan).changed)
        self.assertEqual(self.plan(config).status, PlanStatus.SKIP)

    def test_failure_stops_later_commands(self):
        plan = self.plan(
            [
                {"command": [sys.executable, "-c", "raise SystemExit(7)"]},
                {"command": "touch should-not-run"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "status 7"):
            self.apply(plan)
        self.assertFalse((self.root / "should-not-run").exists())

    def test_timeout(self):
        plan = self.plan(
            {
                "command": [sys.executable, "-c", "import time; time.sleep(5)"],
                "timeout": 0.05,
            }
        )
        with self.assertRaisesRegex(ValueError, "timed out"):
            self.apply(plan)

    def test_script_owned_executable_and_arguments(self):
        script = self.root / "setup.sh"
        script.write_text('#!/bin/sh\nprintf "%s" "$1" > result\n')
        script.chmod(0o755)
        plan = self.plan(
            {"path": "setup.sh", "args": ["argument with spaces"]}, "script"
        )
        self.apply(plan, "script")
        self.assertEqual((self.root / "result").read_text(), "argument with spaces")

    def test_script_validation_and_escape(self):
        (self.root / "not-executable").write_text("echo hello")
        for config in [
            {"path": "missing"},
            {"path": "not-executable"},
            {"path": "../outside"},
        ]:
            with self.assertRaises(ProviderError):
                self.plan(config, "script")

    def test_invalid_options(self):
        for config in [
            {"command": []},
            {"command": ""},
            {"command": "true", "sudo": "yes"},
            {"command": "true", "check": {"shell": "true"}},
            {"command": "true", "timeout": 0},
            {"command": "true", "env": {"BAD=NAME": "value"}},
        ]:
            with self.subTest(config=config), self.assertRaises(ProviderError):
                self.plan(config)

    def test_privilege_and_interactive_metadata(self):
        plan = self.plan({"command": ["true"], "sudo": True, "stdin": True})
        self.assertTrue(plan.elevated)
        self.assertEqual(plan.resources, ("sudo-interactive", "stdin-interactive"))
        with self.assertRaisesRegex(ValueError, "not been authorized"):
            self.apply(plan)
        self.context = replace(self.context, elevation_allowed=True)
        with patch("etchlib.providers.commands.runtime.subprocess.run") as run:
            run.return_value.returncode = 0
            self.apply(plan)
            self.assertEqual(run.call_args.args[0], ["sudo", "-E", "--", "true"])

    def test_default_execution_is_unprivileged_noninteractive(self):
        plan = self.plan({"command": ["true"], "quiet": True})
        self.assertFalse(plan.elevated)
        with patch("etchlib.providers.commands.runtime.subprocess.run") as run:
            run.return_value.returncode = 0
            self.apply(plan)
            self.assertEqual(run.call_args.args[0], ["true"])
            self.assertIsNotNone(run.call_args.kwargs["stdin"])
            self.assertIsNotNone(run.call_args.kwargs["stdout"])

    def test_command_check_respects_environment_path(self):
        (self.root / "python-local").symlink_to(sys.executable)
        plan = self.plan(
            {
                "command": "exit 99",
                "env": {"PATH": "."},
                "check": {"command": "python-local"},
            }
        )
        self.assertEqual(plan.status, PlanStatus.SKIP)
