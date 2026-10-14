"""Timing diagnostics stay separate from command output and execution behavior."""

import contextlib
import io
import sys

from etchlib.cli import main
from tests.planning_fixtures import PlanningFixture


class CliTimingTests(PlanningFixture):
    def test_plan_and_parallel_apply_report_provider_timings(self) -> None:
        self.module(actions=[{"create": ["configured"]}])
        for args in (["plan"], ["apply", "--jobs", "2"]):
            with self.subTest(args=args):
                stdout, stderr = io.StringIO(), io.StringIO()
                with (
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    status = main(args + ["--repo", str(self.root), "--timings"])
                self.assertEqual(status, 0)
                self.assertIn("Provider timings", stderr.getvalue())
                self.assertIn("demo / create / inspect", stderr.getvalue())
                if args[0] == "apply":
                    self.assertIn("demo / create / apply", stderr.getvalue())

    def test_failed_command_is_timed_without_enabling_verbose_output(self) -> None:
        self.module(
            actions=[
                {
                    "shell": {
                        "command": [
                            sys.executable,
                            "-c",
                            "print('private command text'); raise SystemExit(7)",
                        ]
                    }
                }
            ]
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(["apply", "--repo", str(self.root), "--timings"])
        self.assertEqual(status, 1)
        self.assertIn("demo / shell / apply", stderr.getvalue())
        self.assertNotIn("private command text", stderr.getvalue())

    def test_normal_output_has_no_timing_report(self) -> None:
        self.module(actions=[{"create": ["configured"]}])
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as stderr,
        ):
            self.assertEqual(main(["plan", "--repo", str(self.root)]), 0)
        self.assertEqual(stderr.getvalue(), "")
