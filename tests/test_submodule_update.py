"""Explicit CLI setup aligns pins without loading consumer configuration."""

import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.cli import main
from tests.test_link_submodules import SubmoduleFixture, git


class SubmoduleUpdateTests(SubmoduleFixture):
    def test_initialization_preserves_pins_and_skips_configuration(self) -> None:
        root = self.context.repo_root
        before = git(root, "ls-files", "--stage")
        git(root, "submodule", "deinit", "-f", "--all")
        (root / "defaults.conf").write_text("invalid configuration")
        output = io.StringIO()
        with (
            patch.dict(os.environ, GIT_ALLOW_PROTOCOL="file"),
            contextlib.redirect_stdout(output),
            patch(
                "etchlib.cli.load_repository",
                side_effect=AssertionError("loaded configuration"),
            ),
        ):
            self.assertEqual(main(["submodules", "update", "--repo", str(root)]), 0)
            self.assertEqual(main(["submodules", "update", "--repo", str(root)]), 0)
        self.assertIn(str(root), output.getvalue())
        self.assertTrue((self.source / "plugin/.git").exists())
        self.assertEqual(git(root, "ls-files", "--stage"), before)

    def test_recursive_initialization_includes_nested_pins(self) -> None:
        root = self.context.repo_root
        nested = self.root / "nested source"
        nested.mkdir()
        git(nested, "init", "-q")
        git(
            nested,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-qm",
            "nested",
        )
        git(
            self.root / "plugin",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(nested),
            "nested",
        )
        git(
            self.root / "plugin",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qam",
            "add nested",
        )
        git(self.source / "plugin", "fetch", "-q", "origin")
        git(self.source / "plugin", "checkout", "--detach", "-q", "FETCH_HEAD")
        git(root, "add", "modules/vim/bundle/plugin")
        before = git(root, "ls-files", "--stage")
        git(root, "submodule", "deinit", "-f", "--all")
        with (
            patch.dict(os.environ, GIT_ALLOW_PROTOCOL="file"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["submodules", "update", "--repo", str(root)]), 0)
        self.assertTrue((self.source / "plugin/nested/.git").exists())
        self.assertEqual(
            git(self.source / "plugin/nested", "rev-parse", "HEAD"),
            git(nested, "rev-parse", "HEAD"),
        )
        self.assertEqual(git(root, "ls-files", "--stage"), before)

    @unittest.skipIf(os.name == "nt", "POSIX consumer launcher")
    def test_exposed_launcher_uses_consumer_from_unrelated_directory(self) -> None:
        source = Path(__file__).resolve().parents[1]
        root = self.root / "consumer with spaces"
        self.context.repo_root.rename(root)
        shutil.copy2(source / "tests/fixtures/consumer-launcher.sh", root / "etch")
        vendor = root / "vendor/etch"
        vendor.mkdir(parents=True)
        shutil.copy2(source / "etch", vendor / "etch")
        shutil.copytree(
            source / "etchlib",
            vendor / "etchlib",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        exposed = self.root / "exposed-etch"
        exposed.symlink_to(root / "etch")
        git(root, "submodule", "deinit", "-f", "--all")
        result = subprocess.run(
            [str(exposed), "submodules", "update"],
            cwd=self.root,
            env=dict(os.environ, GIT_ALLOW_PROTOCOL="file"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(root.resolve()), result.stdout)
        self.assertTrue((root / "modules/vim/bundle/plugin/.git").exists())

    def test_dirty_worktree_failure_is_preserved(self) -> None:
        root = self.context.repo_root
        checkout = self.source / "plugin"
        (checkout / "owned").write_text("old")
        git(checkout, "add", "owned")
        git(
            checkout,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "new file",
        )
        revision = git(checkout, "rev-parse", "HEAD").strip()
        (checkout / "owned").write_text("keep my edits")
        with contextlib.redirect_stdout(io.StringIO()):
            status = main(["submodules", "update", "--repo", str(root)])
        self.assertNotEqual(status, 0)
        self.assertEqual((checkout / "owned").read_text(), "keep my edits")
        self.assertEqual(git(checkout, "rev-parse", "HEAD").strip(), revision)

    def test_missing_git_and_invalid_repository_are_actionable(self) -> None:
        output = io.StringIO()
        with (
            patch("shutil.which", return_value=None),
            contextlib.redirect_stderr(output),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                main(["submodules", "update", "--repo", str(self.context.repo_root)]), 1
            )
        self.assertIn("Git is required", output.getvalue())
        with (
            tempfile.TemporaryDirectory() as temp,
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["submodules", "update", "--repo", temp]), 1)


class SubmoduleUpdateInvocationTests(unittest.TestCase):
    def test_git_failure_exit_status_is_forwarded(self) -> None:
        from etchlib.submodules import update

        root = Path.cwd().resolve()
        with (
            patch("shutil.which", return_value="git"),
            patch(
                "etchlib.submodules.subprocess.run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, str(root) + "\n", ""),
                    subprocess.CompletedProcess([], 7),
                ],
            ),
        ):
            self.assertEqual(update(root), 7)
