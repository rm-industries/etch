import ast
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from etchlib.cli import main
from etchlib.config import ConfigError, load_repository, read_config

ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "consumer"
        shutil.copytree(ROOT / "examples" / "minimal", self.repo)

    def write(self, relative, value):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(repr(value), encoding="utf-8")

    def test_profile_and_portable_assets(self):
        module = load_repository(self.repo, "developer").modules[0]
        self.assertEqual(module.asset("files/gitconfig").read_text(), "[init]\n    defaultBranch = main\n")
        moved = self.repo.with_name("moved")
        shutil.move(str(self.repo), str(moved))
        self.assertTrue(load_repository(moved).modules[0].asset("files/gitconfig").is_file())

    def test_no_configuration_execution(self):
        path = self.repo / "bad.conf"
        marker = self.repo / "executed"
        path.write_text("__import__('pathlib').Path({!r}).touch()".format(str(marker)))
        with self.assertRaises(ConfigError):
            read_config(path)
        self.assertFalse(marker.exists())

    def test_bad_versions_and_shapes(self):
        for value in [[], {1: "bad"}, {}, {"schema_version": True}, {"schema_version": 2}]:
            with self.subTest(value=value):
                self.write("bad.conf", value)
                with self.assertRaises(ConfigError):
                    read_config(self.repo / "bad.conf")

    def test_syntax_error_has_path(self):
        path = self.repo / "bad.conf"
        path.write_text("{")
        with self.assertRaisesRegex(ConfigError, "bad.conf"):
            read_config(path)

    def test_selection_order(self):
        self.write("modules/zsh/module.conf", {"schema_version": 1, "name": "zsh"})
        self.assertEqual([m.name for m in load_repository(self.repo, selected=["zsh", "git"]).modules], ["zsh", "git"])
        self.assertEqual([m.name for m in load_repository(self.repo).modules], ["git", "zsh"])

    def test_selection_errors(self):
        for kwargs in [{"profile": "developer", "selected": ["git"]}, {"selected": ["missing"]}, {"selected": ["git", "git"]}, {"profile": "../escape"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfigError):
                load_repository(self.repo, **kwargs)

    def test_module_shape_and_identity(self):
        for extra in [{"name": "other"}, {"actions": "bad"}, {"requires": ["../bad"]}, {"facts": []}]:
            self.write("modules/git/module.conf", dict({"schema_version": 1, "name": "git"}, **extra))
            with self.subTest(extra=extra), self.assertRaises(ConfigError):
                load_repository(self.repo)

    def test_duplicate_identity(self):
        self.write("modules/zsh/module.conf", {"schema_version": 1, "name": "git"})
        with self.assertRaisesRegex(ConfigError, "duplicate module"):
            load_repository(self.repo)

    def test_assets_cannot_escape(self):
        module = load_repository(self.repo).modules[0]
        for value in ["../../outside", "/tmp/outside", ""]:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                module.asset(value)
        (module.root / "outside").symlink_to(self.repo)
        with self.assertRaises(ConfigError):
            module.asset("outside/defaults.conf")

    def test_invalid_defaults(self):
        self.write("defaults.conf", {"schema_version": 1, "defaults": {"link": []}})
        with self.assertRaises(ConfigError):
            load_repository(self.repo)

    def test_doctor_honestly_reports_partial_validation(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = main(["doctor", "--repo", str(self.repo), "--profile", "developer"])
        self.assertEqual(status, 0)
        self.assertIn("not checked yet", out.getvalue())

    def test_doctor_failure(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            self.assertEqual(main(["doctor", "--repo", str(self.repo), "missing"]), 1)
        self.assertIn("missing modules", out.getvalue())

    def test_launcher_outside_checkout(self):
        result = subprocess.run([sys.executable, "-S", str(ROOT / "etch"), "--version"], cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "Etch 0.1.0-dev")

    def test_unsupported_python_guard(self):
        result = subprocess.run([sys.executable, "-c", "import sys, runpy; sys.version_info = (3, 8); runpy.run_path(sys.argv[1], run_name='__main__')", str(ROOT / "etch")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Python 3.9 or newer", result.stderr)

    def test_python39_grammar(self):
        for path in list((ROOT / "etchlib").glob("*.py")) + [ROOT / "etch"]:
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
