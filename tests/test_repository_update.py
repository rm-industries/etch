"""Consumer updates delegate Git policy and stop before syncing after failures."""

import contextlib
import io
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.cli import main
from tests.test_link_submodules import SubmoduleFixture, git


class RepositoryUpdateTests(SubmoduleFixture):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.context.repo_root
        (self.repo / "local.txt").write_text("original\n")
        git(self.repo, "add", "local.txt")
        self.commit(self.repo, "initial file")
        self.upstream = self.root / "upstream"
        git(self.root, "clone", "-q", str(self.repo), str(self.upstream))
        git(self.repo, "remote", "add", "origin", str(self.upstream))
        git(self.repo, "fetch", "-q", "origin")
        branch = git(self.repo, "branch", "--show-current").strip()
        git(self.repo, "branch", "--set-upstream-to=origin/" + branch)

    @staticmethod
    def commit(root: Path, message: str) -> None:
        git(
            root,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qam",
            message,
        )

    def update(self) -> int:
        with (
            patch.dict(os.environ, GIT_ALLOW_PROTOCOL="file"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return main(["update", "--repo", str(self.repo)])

    def advance(self) -> None:
        (self.upstream / "new.txt").write_text("upstream")
        git(self.upstream, "add", "new.txt")
        self.commit(self.upstream, "new file")

    def test_pull_restores_local_edits_without_loading_configuration(self) -> None:
        self.advance()
        (self.repo / "local.txt").write_text("local edits\n")
        (self.repo / "untracked.txt").write_text("keep")
        with patch(
            "etchlib.cli.load_repository",
            side_effect=AssertionError("loaded configuration"),
        ):
            self.assertEqual(self.update(), 0)
        self.assertTrue((self.repo / "new.txt").exists())
        self.assertEqual((self.repo / "local.txt").read_text(), "local edits\n")
        self.assertEqual((self.repo / "untracked.txt").read_text(), "keep")

    def test_divergence_stops_without_merging_or_syncing(self) -> None:
        self.advance()
        (self.repo / "local.txt").write_text("committed locally\n")
        self.commit(self.repo, "local commit")
        before = git(self.repo, "rev-parse", "HEAD")
        with patch(
            "etchlib.repository_update.update_submodules",
            side_effect=AssertionError("synced after failure"),
        ):
            self.assertNotEqual(self.update(), 0)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), before)

    def test_restoration_conflict_stops_before_syncing(self) -> None:
        (self.upstream / "local.txt").write_text("upstream edits\n")
        self.commit(self.upstream, "upstream edit")
        (self.repo / "local.txt").write_text("local edits\n")
        with patch(
            "etchlib.repository_update.update_submodules",
            side_effect=AssertionError("synced after conflict"),
        ):
            self.assertNotEqual(self.update(), 0)
        self.assertTrue(
            git(self.repo, "diff", "--name-only", "--diff-filter=U").strip()
        )
        self.assertTrue(git(self.repo, "stash", "list").strip())

    def test_pulled_gitlink_is_synchronized(self) -> None:
        plugin = self.root / "plugin"
        self.commit_empty(plugin, "new plugin revision")
        revision = git(plugin, "rev-parse", "HEAD")
        with patch.dict(os.environ, GIT_ALLOW_PROTOCOL="file"):
            git(self.upstream, "submodule", "update", "--init", "--recursive")
        checkout = self.upstream / "modules/vim/bundle/plugin"
        git(checkout, "fetch", "-q", "origin")
        git(checkout, "checkout", "-q", "--detach", revision.strip())
        git(self.upstream, "add", "modules/vim/bundle/plugin")
        self.commit(self.upstream, "new pin")
        self.assertEqual(self.update(), 0)
        self.assertEqual(git(self.source / "plugin", "rev-parse", "HEAD"), revision)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    @staticmethod
    def commit_empty(root: Path, message: str) -> None:
        git(
            root,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-qm",
            message,
        )

    def test_untracked_collision_is_not_overwritten(self) -> None:
        self.advance()
        (self.repo / "new.txt").write_text("untracked local file")
        with patch(
            "etchlib.repository_update.update_submodules",
            side_effect=AssertionError("synced after failure"),
        ):
            self.assertNotEqual(self.update(), 0)
        self.assertEqual((self.repo / "new.txt").read_text(), "untracked local file")

    @unittest.skipIf(os.name == "nt", "POSIX consumer launcher")
    def test_exposed_launcher_updates_consumer_from_another_directory(self) -> None:
        self.advance()
        moved = self.root / "consumer with spaces"
        self.repo.rename(moved)
        self.repo = moved
        source = Path(__file__).resolve().parents[1]
        shutil.copy2(source / "tests/fixtures/consumer-launcher.sh", moved / "etch")
        vendor = moved / "vendor/etch"
        vendor.mkdir(parents=True)
        shutil.copy2(source / "etch", vendor / "etch")
        shutil.copytree(
            source / "etchlib",
            vendor / "etchlib",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (moved / "defaults.conf").write_text("invalid configuration")
        exposed = self.root / "exposed-etch"
        exposed.symlink_to(moved / "etch")
        result = subprocess.run(
            [str(exposed), "update"],
            cwd=self.root,
            env=dict(os.environ, GIT_ALLOW_PROTOCOL="file"),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((moved / "new.txt").exists())
        self.assertIn(str(moved.resolve()), result.stdout)

    def test_submodule_failure_status_is_returned(self) -> None:
        with patch("etchlib.repository_update.update_submodules", return_value=37):
            self.assertEqual(self.update(), 37)
