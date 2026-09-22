"""Copy boundaries, pinned provenance, and non-executing reports."""

import contextlib
import io
import json
import shutil
from unittest.mock import patch

from etchlib.cli import main
from tests.import_fixtures import ImportFixture


class ImportCopyTests(ImportFixture):
    def test_pinned_copy_and_repeatability(self) -> None:
        executable = self.module_path / "setup.py"
        executable.write_text("raise RuntimeError('must not execute')\n")
        executable.chmod(0o755)
        pinned = self.save()
        (self.module_path / "files/asset").write_text("new branch content")
        self.save()
        output = self.run_import(pinned)
        destination = self.consumer / "modules/demo"
        self.assertEqual((destination / "files/asset").read_text(), "original\n")
        self.assertEqual((destination / "setup.py").stat().st_mode & 0o777, 0o755)
        metadata = json.loads((destination / ".etch-import.json").read_text())
        self.assertEqual(metadata["resolved_commit"], pinned)
        self.assertEqual(metadata["source"], "https://github.com/example/dotfiles.git")
        self.assertIn("setup.py", output)
        first = {
            str(p.relative_to(destination)): p.read_bytes()
            for p in destination.rglob("*")
            if p.is_file()
        }
        shutil.rmtree(destination)
        self.run_import(pinned)
        self.assertEqual(
            first,
            {
                str(p.relative_to(destination)): p.read_bytes()
                for p in destination.rglob("*")
                if p.is_file()
            },
        )

    def test_tag_head_and_no_provenance(self) -> None:
        self.git("tag", "-a", "v1", "-m", "Tag")
        output = self.run_import("refs/tags/v1", provenance=False)
        self.assertIn(self.commit, output)
        self.assertFalse((self.consumer / "modules/demo/.etch-import.json").exists())

    def test_cli_reports_without_loading_plugins_or_running_code(self) -> None:
        self.config(
            requires=["absent"],
            after=["optional"],
            facts={"custom": {"external.fact": {}}},
            actions=[
                {"external.action": {}},
                {"shell": {"command": "touch NEVER"}},
                {
                    "installer": {
                        "url": "https://user:secret@example.invalid/install?token=secret"
                    }
                },
            ],
        )
        (self.module_path / "etch_plugin.py").write_text(
            "raise RuntimeError('executed')"
        )
        (self.consumer / "defaults.conf").write_text(
            repr({"schema_version": 1, "plugins": ["untrusted"]})
        )
        self.save()
        out = io.StringIO()
        with (
            patch("etchlib.cli.load_plugins", side_effect=AssertionError("loaded")),
            contextlib.redirect_stdout(out),
        ):
            result = main(
                [
                    "import",
                    "github:example/dotfiles",
                    "--path",
                    "modules/demo",
                    "--repo",
                    str(self.consumer),
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("plugin availability unverified", out.getvalue())
        self.assertIn("setup required", out.getvalue())
        self.assertIn("ordering warning", out.getvalue())
        self.assertIn("etch_plugin.py", out.getvalue())
        self.assertNotIn("secret", out.getvalue())
        self.assertFalse((self.consumer / "NEVER").exists())

    def test_existing_destination_refused_before_acquisition(self) -> None:
        target = self.consumer / "modules/demo"
        target.mkdir(parents=True)
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    target.rmdir()
                    target.symlink_to("absent")
                with (
                    patch(
                        "etchlib.importing.copy.Git",
                        side_effect=AssertionError("fetched"),
                    ),
                    self.assertRaisesRegex(ValueError, "already exists"),
                ):
                    self.run_import()
                self.assertTrue(target.is_dir() or target.is_symlink())

    def test_malformed_configuration_leaves_no_destination(self) -> None:
        (self.module_path / "module.conf").write_text(
            "{'schema_version': 1, 'name': 'demo', 'name': 'demo'}"
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "structural validation"):
            self.run_import()
        self.assertFalse((self.consumer / "modules/demo").exists())

    def test_missing_ref_and_directory(self) -> None:
        with self.assertRaisesRegex(ValueError, "fetch failed"):
            self.run_import("refs/heads/absent")
        shutil.rmtree(self.module_path)
        (self.upstream / "other").write_text("unrelated")
        self.save()
        with self.assertRaisesRegex(ValueError, "not a Git directory"):
            self.run_import()
        self.assertFalse((self.consumer / "modules/demo").exists())

    def test_publication_failure_cleans_owned_destination(self) -> None:
        with (
            patch(
                "etchlib.importing.copy.shutil.move", side_effect=OSError("interrupted")
            ),
            self.assertRaisesRegex(OSError, "interrupted"),
        ):
            self.run_import()
        self.assertFalse((self.consumer / "modules/demo").exists())

    def test_filter_fallback_is_reported(self) -> None:
        self.git("config", "uploadpack.allowFilter", "false")
        self.assertIn("did not support blob filtering", self.run_import())
