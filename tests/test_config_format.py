"""Configuration formatting preserves data and ignores editor preferences."""

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from etchlib.cli import main
from etchlib.config import ConfigError, read_config
from etchlib.config_format import format_repository


class ConfigFormatTests(unittest.TestCase):
    def test_two_space_format_is_idempotent_and_editorconfig_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            module = root / "modules/git/module.conf"
            profile = root / "profiles/developer.conf"
            module.parent.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            module.write_text(
                repr(
                    {
                        "schema_version": 1,
                        "name": "git",
                        "actions": [{"create": ["one", "two"]}],
                    }
                )
            )
            profile.write_text(
                repr({"schema_version": 1, "name": "developer", "modules": ["git"]})
            )
            before = [read_config(path) for path in (module, profile)]
            (root / ".editorconfig").write_text("[*]\nindent_size = 8\n")
            self.assertEqual(format_repository(root, check=True), [module, profile])
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["format", "--check", "--repo", str(root)]), 1)
            self.assertEqual([read_config(path) for path in (module, profile)], before)
            self.assertEqual(format_repository(root), [module, profile])
            self.assertIn("\n  'name': 'git',\n", module.read_text())
            self.assertIn("'create': ['one', 'two']", module.read_text())
            self.assertEqual([read_config(path) for path in (module, profile)], before)
            self.assertEqual(format_repository(root), [])
            self.assertEqual(format_repository(root, check=True), [])
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["format", "--check", "--repo", str(root)]), 0)
            profile.write_text(repr(before[1]))
            with redirect_stdout(StringIO()):
                self.assertEqual(
                    main(["format", "profiles/developer.conf", "--repo", str(root)]),
                    0,
                )
            self.assertEqual(format_repository(root, check=True), [])
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["validate", "--repo", str(root)]), 0)

    def test_comments_survive_and_unsafe_placement_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            module = root / "modules/git/module.conf"
            profile = root / "profiles/developer.conf"
            module.parent.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            module.write_text("{'schema_version': 1, 'name': 'git'}")
            profile.write_text(
                "# profile\n{'schema_version': 1, # keep this\n 'name': 'déveloper'}"
            )
            self.assertEqual(format_repository(root), [module, profile])
            self.assertIn("# profile", profile.read_text())
            self.assertIn("# keep this", profile.read_text())
            self.assertEqual(format_repository(root), [])
            module.write_text("{'schema_version': 1, 'name': 'git'}")
            profile.write_text(
                "{'schema_version': 1, 'name': # cannot place\n 'developer'}"
            )
            original = module.read_text()
            with self.assertRaisesRegex(ConfigError, "cannot safely place"):
                format_repository(root)
            self.assertEqual(module.read_text(), original)

    def test_long_array_splits_and_profile_validation_is_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            module = root / "modules/git/module.conf"
            profile = root / "profiles/developer.conf"
            module.parent.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            module.write_text(
                repr(
                    {
                        "schema_version": 1,
                        "name": "git",
                        "actions": [{"shell": {"command": ["tool", "x" * 115]}}],
                    }
                )
            )
            profile.write_text(
                repr({"schema_version": 1, "name": "developer", "modules": ["missing"]})
            )
            format_repository(root)
            self.assertIn("'command': [\n", module.read_text())
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(["validate", "--repo", str(root)]), 1)


if __name__ == "__main__":
    unittest.main()
