"""Exercise real consumer layouts with only Python available at runtime."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.plugin_fixtures import write_plugin

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="etch bootstrap ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.consumer = self.root / "consumer repo"
        shutil.copytree(ROOT / "examples" / "minimal", self.consumer)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.python = self.bin / "python3"
        self.python.symlink_to(sys.executable)
        self.env = dict(os.environ, PATH=str(self.bin), PYTHONNOUSERSITE="1")
        self.env.pop("PYTHONPATH", None)
        self.env.pop("PYTHONHOME", None)

    def vendor(self, destination=None):
        destination = destination or self.consumer / "vendor" / "etch"
        destination.mkdir(parents=True)
        shutil.copy2(ROOT / "etch", destination / "etch")
        shutil.copytree(
            ROOT / "etchlib",
            destination / "etchlib",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        return destination

    def run_install(self, *args, consumer=None):
        return subprocess.run(
            [str((consumer or self.consumer) / "install"), *args],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def test_vendored_source_with_python_only_path(self):
        self.vendor()
        result = self.run_install("doctor", "--profile", "developer")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.consumer.resolve()), result.stdout)
        self.assertIn("  git", result.stdout)

    def test_missing_python(self):
        self.python.unlink()
        result = self.run_install("--version")
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires Python 3.9 or newer", result.stderr)

    def test_missing_vendor(self):
        result = self.run_install("--version")
        self.assertEqual(result.returncode, 1)
        self.assertIn("source is missing from vendor/etch", result.stderr)

    def test_arguments_and_exit_status_are_preserved(self):
        self.vendor()
        result = self.run_install("doctor", "missing module")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing modules: missing module", result.stderr)
        result = self.run_install("--unknown-option")
        self.assertEqual(result.returncode, 2)

    def test_startup_does_not_connect_to_network(self):
        vendor = self.vendor()
        # An audit hook fails the process if any startup path attempts socket I/O.
        probe = """import runpy, sys
def reject_network(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('network access attempted: ' + event)
sys.addaudithook(reject_network)
sys.path.insert(0, sys.argv[1])
entry = sys.argv[1] + '/etch'
sys.argv = [entry, 'doctor', '--repo', sys.argv[2], '--profile', 'developer']
runpy.run_path(entry, run_name='__main__')
"""
        result = subprocess.run(
            [sys.executable, "-S", "-c", probe, str(vendor), str(self.consumer)],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Configuration structure OK", result.stdout)

    @unittest.skipUnless(
        shutil.which("git"),
        "Git is needed to construct the submodule distribution fixture",
    )
    def test_recursive_clone_with_pinned_submodule(self):
        git = shutil.which("git")
        env = dict(
            os.environ,
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_AUTHOR_NAME="Etch test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="Etch test",
            GIT_COMMITTER_EMAIL="test@example.invalid",
        )

        def run_git(cwd, *args):
            return subprocess.run(
                [git, "-c", "protocol.file.allow=always", *args],
                cwd=cwd,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()

        source = self.vendor(self.root / "etch source")
        run_git(source, "init")
        run_git(source, "add", ".")
        run_git(source, "commit", "-m", "Test engine snapshot")
        revision = run_git(source, "rev-parse", "HEAD")
        plugin = write_plugin(self.root / "plugin source")
        run_git(plugin, "init")
        run_git(plugin, "add", ".")
        run_git(plugin, "commit", "-m", "Test plugin snapshot")
        plugin_revision = run_git(plugin, "rev-parse", "HEAD")
        run_git(self.consumer, "init")
        run_git(self.consumer, "submodule", "add", str(source), "vendor/etch")
        run_git(self.consumer, "submodule", "add", str(plugin), "vendor/example")
        (self.consumer / "defaults.conf").write_text(
            "{'schema_version': 1, 'plugins': ['vendor/example']}"
        )
        run_git(self.consumer, "add", ".")
        run_git(self.consumer, "commit", "-m", "Test consumer")
        clone = self.root / "cloned consumer"
        run_git(
            self.root, "clone", "--recurse-submodules", str(self.consumer), str(clone)
        )
        self.assertEqual(
            run_git(clone / "vendor" / "etch", "rev-parse", "HEAD"), revision
        )
        self.assertEqual(
            run_git(clone / "vendor" / "example", "rev-parse", "HEAD"), plugin_revision
        )
        # Git was used only for fixture construction. Runtime PATH contains Python alone.
        result = self.run_install("doctor", "--profile", "developer", consumer=clone)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(clone.resolve()), result.stdout)
        self.assertIn("Plugin example 1.2.3 (API 1)", result.stdout)
