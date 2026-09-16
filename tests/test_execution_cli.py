import contextlib
import io
import subprocess
import sys
from pathlib import Path

from etchlib.cli import main
from tests.planning_fixtures import PlanningFixture


class ApplyCliTests(PlanningFixture):
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
        self.assertIn("CHANGED a:action[0]", output)
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
        self.assertIn("FAILED demo:action[0]", output)
        self.assertIn("BLOCKED demo:action[1]", output)
        self.assertFalse((self.root / "not-created").exists())

    def test_false_conditions_are_reported_as_skips(self) -> None:
        self.module(when={"os": "never"}, actions=[{"missing": {}}])
        status, output = self.run_cli()
        self.assertEqual(status, 0, output)
        self.assertIn("SKIPPED", output)
