import contextlib
import io
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.cli import main
from etchlib.providers.filesystem.create import CreateProvider
from tests.planning_fixtures import PlanningFixture


class ApplyCliTests(PlanningFixture):
    def test_progress_precedes_summary_and_is_flushed(self) -> None:
        class Output(io.StringIO):
            flushes = 0

            def flush(self) -> None:
                self.flushes += 1

        for jobs in ("1", "2"):
            with self.subTest(jobs=jobs):
                self.module("a", actions=[{"create": ["a-" + jobs]}])
                self.module("b", actions=[{"create": ["b-" + jobs]}])
                output = Output()
                inspect = CreateProvider.inspect

                def checking(
                    provider: CreateProvider,
                    config: Any,
                    context: Any,
                    output: Output = output,
                    inspect: Any = inspect,
                ) -> Any:
                    self.assertIn("Checking a...", output.getvalue())
                    return inspect(provider, config, context)

                with (
                    contextlib.redirect_stdout(output),
                    patch.object(CreateProvider, "inspect", checking),
                ):
                    status = main(["apply", "--repo", str(self.root), "--jobs", jobs])
                self.assertEqual(status, 0, output.getvalue())
                lines = output.getvalue().splitlines()
                self.assertEqual(
                    lines[:3], ["Preparing apply...", "Checking a...", "Checking b..."]
                )
                self.assertIn("Applying a...", lines)
                self.assertIn("Applying b...", lines)
                self.assertIn("Apply complete:", lines[-1])
                self.assertEqual(lines.count("Checking a..."), 1)
                self.assertEqual(lines.count("Checking b..."), 1)
                self.assertEqual(lines.count("Rechecking remaining actions..."), 1)
                self.assertEqual(output.flushes, 6)

    def test_verbose_reaches_serial_and_parallel_commands(self) -> None:
        self.module(
            "a",
            actions=[
                {"shell": {"command": [sys.executable, "-c", "print('vendor banner')"]}}
            ],
        )
        engine = Path(__file__).resolve().parents[1] / "etch"
        for jobs in ("1", "2"):
            for verbose in (False, True):
                with self.subTest(jobs=jobs, verbose=verbose):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-S",
                            str(engine),
                            "apply",
                            "--repo",
                            str(self.root),
                            "--jobs",
                            jobs,
                        ]
                        + (["--verbose"] if verbose else []),
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    self.assertEqual("vendor banner" in result.stdout, verbose)

    def run_cli(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status = main(["apply", "--repo", str(self.root), *args])
        return status, output.getvalue()

    def test_direct_module_selection_and_idempotence(self) -> None:
        self.module("a", actions=[{"create": ["a-directory"]}])
        self.module("b", actions=[{"create": ["b-directory"]}])
        status, output = self.run_cli("a")
        self.assertEqual(status, 0, output)
        self.assertIn("a:\n  CHANGED", output)
        self.assertTrue((self.root / "a-directory").is_dir())
        self.assertFalse((self.root / "b-directory").exists())
        self.assertIn("SKIPPED", self.run_cli("a")[1])

    def test_profile_apply_with_site_packages_disabled(self) -> None:
        self.module("a", actions=[{"create": ["a-directory"]}])
        self.module("b", actions=[{"create": ["b-directory"]}])
        self.write(
            "profiles/dev.conf", {"schema_version": 1, "name": "dev", "modules": ["b"]}
        )
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(Path(__file__).resolve().parents[1] / "etch"),
                "apply",
                "--jobs",
                "2",
                "--repo",
                str(self.root),
                "--profile",
                "dev",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse((self.root / "a-directory").exists())
        self.assertTrue((self.root / "b-directory").is_dir())

    def test_failure_returns_nonzero_and_reports_blocked_work(self) -> None:
        self.module(
            actions=[
                {"shell": {"command": [sys.executable, "-c", "raise SystemExit(7)"]}},
                {"create": ["not-created"]},
            ]
        )
        status, output = self.run_cli()
        self.assertEqual(status, 1)
        self.assertIn("demo:\n  FAILED", output)
        self.assertIn("BLOCKED", output)
        self.assertFalse((self.root / "not-created").exists())

    def test_false_conditions_are_reported_as_skips(self) -> None:
        self.module(when={"os": "never"}, actions=[{"missing": {}}])
        status, output = self.run_cli()
        self.assertEqual(status, 0, output)
        self.assertIn("SKIPPED", output)
