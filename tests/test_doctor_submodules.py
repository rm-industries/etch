"""Doctor checks every pinned submodule, including unselected/plugin assets."""

import contextlib
import io
import shutil
from pathlib import Path
from unittest.mock import patch

from etchlib.cli import main
from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.diagnostics.doctor import diagnose
from tests.test_link_submodules import SubmoduleFixture, git


class DoctorSubmoduleTests(SubmoduleFixture):
    def prepare(self) -> Path:
        root = self.context.repo_root
        # Remove provider actions so only a repository-wide check can find this gap.
        (self.module / "module.conf").write_text(
            repr({"schema_version": 1, "name": "vim", "actions": []})
        )
        return root

    def test_missing_submodule_is_reported_without_provider_use_or_mutation(
        self,
    ) -> None:
        root = self.prepare()
        git(root, "submodule", "deinit", "-f", "--all")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status = main(["doctor", "--repo", str(root)])
        self.assertEqual(status, 1)
        self.assertIn("modules/vim/bundle/plugin", output.getvalue())
        self.assertIn("git submodule update --init --recursive", output.getvalue())
        self.assertFalse((self.source / "plugin/.git").exists())
        self.assertFalse(self.target.exists())
        diagnosis = diagnose(load_repository(root), core_registry())
        self.assertTrue(any("submodule" in error for error in diagnosis.errors))

    def test_initialized_submodule_passes_and_wrong_revision_fails(self) -> None:
        root = self.prepare()
        self.assertEqual(diagnose(load_repository(root), core_registry()).errors, ())
        git(
            self.source / "plugin",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-qm",
            "drift",
        )
        self.assertTrue(
            any(
                "pinned revision" in error
                for error in diagnose(load_repository(root), core_registry()).errors
            )
        )

    def test_missing_plugin_submodule_is_reported_before_plugin_loading(self) -> None:
        root = self.prepare()
        git(root, "submodule", "deinit", "-f", "--all")
        (root / "defaults.conf").write_text(
            repr({"schema_version": 1, "plugins": ["modules/vim/bundle/plugin"]})
        )
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
            patch(
                "etchlib.cli.load_plugins",
                side_effect=AssertionError("plugin load preceded diagnostics"),
            ),
        ):
            self.assertEqual(main(["doctor", "--repo", str(root)]), 1)
        self.assertIn("git submodule update", output.getvalue())

    def test_git_unavailable_is_actionable(self) -> None:
        root = self.prepare()
        original = shutil.which
        with patch(
            "shutil.which",
            side_effect=lambda name: None if name == "git" else original(name),
        ):
            diagnosis = diagnose(load_repository(root), core_registry())
        self.assertTrue(
            any("Submodules not verified" in warning for warning in diagnosis.warnings)
        )
