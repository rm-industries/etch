"""Reject unsafe sources and tree entries before any completed publication."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.importing.git import Git
from etchlib.importing.source import parse
from tests.import_fixtures import ImportFixture


class ImportSourceTests(unittest.TestCase):
    def test_invalid_source_ref_and_paths(self) -> None:
        for source in (
            "git@github.com:owner/repo",
            "file:///tmp/repo",
            "http://example.org/repo",
            "https://user:pass@example.org/repo",
            "https://example.org/repo?token=x",
            "https://example.org/repo#path",
            "github:owner/repo/path",
            "github:owner/..",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse(source, "HEAD", "modules/demo")
        for ref in (
            "main",
            "HEAD~1",
            "refs/heads/../main",
            "refs/heads/a.lock",
            "refs/heads/a:b",
            "refs/tags/",
            "deadbeef",
        ):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                parse("github:o/r", ref, "modules/demo")
        for path in (
            "/modules/demo",
            "modules/../demo",
            "modules//demo",
            "modules/demo/",
            ".",
            "modules\\demo",
            "modules/.GIT/demo",
            "modules/\ndemo",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                parse("github:o/r", "HEAD", path)

    def test_missing_and_old_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch("etchlib.importing.git.shutil.which", return_value=None),
                self.assertRaisesRegex(ValueError, "requires Git"),
            ):
                Git(Path(temporary))
            with (
                patch.object(Git, "run", return_value=b"git version 2.24.0"),
                self.assertRaisesRegex(ValueError, "requires Git"),
            ):
                Git(Path(temporary))

    def test_timeout_and_git_configuration_isolation(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(
                "os.environ",
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "http.sslVerify",
                    "GIT_CONFIG_VALUE_0": "false",
                    "GIT_SSH_COMMAND": "evil",
                },
            ),
        ):
            git = Git(Path(temporary))
            self.assertNotIn("GIT_CONFIG_COUNT", git.env)
            self.assertNotIn("GIT_SSH_COMMAND", git.env)
            self.assertEqual(git.env["GIT_ALLOW_PROTOCOL"], "https")
            with (
                patch("etchlib.importing.git.subprocess.Popen") as popen,
                patch("etchlib.importing.git.os.killpg") as kill,
            ):
                process = popen.return_value.__enter__.return_value
                process.communicate.side_effect = subprocess.TimeoutExpired("git", 1)
                with self.assertRaisesRegex(ValueError, "120 seconds"):
                    git.run("fetch")
                kill.assert_called_once()
                process.wait.assert_called_once()


class ImportBoundaryTests(ImportFixture):
    def test_symlink_lfs_and_reserved_provenance(self) -> None:
        asset = self.module_path / "files/asset"
        asset.unlink()
        asset.symlink_to("../../outside")
        self.save()
        with self.assertRaisesRegex(ValueError, "symlinks/submodules"):
            self.run_import()
        asset.unlink()
        asset.write_text(
            "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n"
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "LFS pointer"):
            self.run_import()
        asset.write_text("ordinary")
        (self.module_path / ".etch-import.json").write_text("{}")
        self.save()
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.run_import()
        self.assertFalse((self.consumer / "modules/demo").exists())

    def test_gitlink_rejected(self) -> None:
        self.git(
            "update-index",
            "--add",
            "--cacheinfo",
            "160000",
            self.commit,
            "modules/demo/submodule",
        )
        self.git("commit", "-m", "Gitlink")
        with self.assertRaisesRegex(ValueError, "symlinks/submodules"):
            self.run_import()

    def test_tree_collision_without_filesystem_checkout(self) -> None:
        # Build a case-colliding tree even on case-insensitive macOS volumes.
        oid = self.git("rev-parse", "HEAD:modules/demo/files/asset")
        self.git(
            "update-index",
            "--add",
            "--cacheinfo",
            "100644",
            oid,
            "modules/demo/FILES/other",
        )
        self.git("commit", "-m", "Collision")
        with self.assertRaisesRegex(ValueError, "collision"):
            self.run_import()

    def test_file_and_total_limits(self) -> None:
        for limit in ("MAX_FILE", "MAX_TOTAL", "MAX_FILES"):
            with (
                self.subTest(limit=limit),
                patch("etchlib.importing.tree." + limit, 1),
                self.assertRaisesRegex(ValueError, "limits"),
            ):
                self.run_import()
        self.assertFalse((self.consumer / "modules/demo").exists())

    def test_parent_symlink_refused(self) -> None:
        (self.consumer / "modules").symlink_to(self.upstream / "modules")
        with self.assertRaisesRegex(ValueError, "real directory"):
            self.run_import()
        self.assertTrue((self.module_path / "module.conf").exists())

    def test_interrupted_retrieval_does_not_publish(self) -> None:
        with (
            patch(
                "etchlib.importing.copy.materialize", side_effect=OSError("interrupted")
            ),
            self.assertRaisesRegex(OSError, "interrupted"),
        ):
            self.run_import()
        self.assertFalse((self.consumer / "modules").exists())

    def test_noncommit_tag_and_missing_configuration(self) -> None:
        tree = self.git("rev-parse", "HEAD^{tree}")
        self.git("tag", "not-commit", tree)
        with self.assertRaisesRegex(ValueError, "rev-parse failed"):
            self.run_import("refs/tags/not-commit")
        (self.module_path / "module.conf").unlink()
        self.save()
        with self.assertRaisesRegex(ValueError, "missing module.conf"):
            self.run_import()

    def test_literal_configuration_never_executes(self) -> None:
        marker = self.root / "executed"
        (self.module_path / "module.conf").write_text(
            "__import__('pathlib').Path({!r}).touch()".format(str(marker))
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "structural validation"):
            self.run_import()
        self.assertFalse(marker.exists())

    def test_branch_provenance_tracks_fetched_snapshot(self) -> None:
        (self.module_path / "files/asset").write_text("moved")
        moved = self.save()
        self.run_import("refs/heads/main")
        metadata = (self.consumer / "modules/demo/.etch-import.json").read_text()
        self.assertIn(moved, metadata)
        self.assertNotIn(self.commit, metadata)
        shutil.rmtree(self.consumer / "modules/demo")
        self.run_import(self.commit)
        self.assertEqual(
            (self.consumer / "modules/demo/files/asset").read_text(), "original\n"
        )
