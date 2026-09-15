import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etchlib.config import (
    ConfigError,
    compose_defaults,
    destination,
    load_repository,
    read_config,
)

ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "examples/minimal", self.repo, dirs_exist_ok=True)

    def write(self, relative, text):
        path = self.repo / relative
        path.write_text(text, encoding="utf-8")
        return path

    def test_duplicate_keys_rejected_at_every_depth(self):
        for text in [
            "{'schema_version': 1, 'schema_version': 1}",
            "{'schema_version': 1, 'actions': [{'link': {'x': 'a', 'x': 'b'}}]}",
        ]:
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(ConfigError, "duplicate key"),
            ):
                read_config(self.write("bad.conf", text))

    def test_unsupported_literals_and_nested_key_types(self):
        for literal in ["(1, 2)", "{1, 2}", "b'abc'", "1j", "...", "{1: 'bad'}"]:
            with self.subTest(literal=literal), self.assertRaises(ConfigError):
                read_config(
                    self.write(
                        "bad.conf", "{'schema_version': 1, 'x': " + literal + "}"
                    )
                )

    def test_comments_trailing_commas_and_data_values(self):
        path = self.write(
            "valid.conf",
            "{ # comment\n 'schema_version': 1, 'x': [True, None, 2, 1.5, 'text'], }",
        )
        self.assertEqual(read_config(path)["x"], [True, None, 2, 1.5, "text"])

    def test_unknown_fields_are_not_silently_ignored(self):
        cases = [
            ("defaults.conf", "{'schema_version': 1, 'defauts': {}}"),
            (
                "modules/git/module.conf",
                "{'schema_version': 1, 'name': 'git', 'action': []}",
            ),
            (
                "profiles/developer.conf",
                "{'schema_version': 1, 'name': 'developer', 'modules': ['git'], 'when': {}}",
            ),
        ]
        for relative, text in cases:
            path = self.repo / relative
            original = path.read_text()
            self.write(relative, text)
            with (
                self.subTest(relative=relative),
                self.assertRaisesRegex(ConfigError, "unknown fields"),
            ):
                load_repository(self.repo, "developer")
            path.write_text(original)

    def test_action_envelopes(self):
        for action in [
            {},
            {"": {}},
            {"when": {"os": "linux"}},
            {"link": {}, "create": []},
            {"link": {}, "refresh": "fact"},
            {"link": {}, "when": []},
        ]:
            config = {"schema_version": 1, "name": "git", "actions": [action]}
            self.write("modules/git/module.conf", repr(config))
            with (
                self.subTest(action=action),
                self.assertRaisesRegex(ConfigError, "actions"),
            ):
                load_repository(self.repo)

    def test_external_provider_payload_preserved(self):
        action = {
            "custom": {"items": ["one"]},
            "when": {"os": "linux"},
            "refresh": ["installed"],
        }
        config = {
            "schema_version": 1,
            "name": "git",
            "actions": [action],
            "facts": {"installed": {"custom_fact": {}}},
        }
        self.write("modules/git/module.conf", repr(config))
        self.assertEqual(load_repository(self.repo).modules[0].config, config)

    def test_fact_envelopes(self):
        for fact in [[], {}, {"command": "git", "env": "HOME"}]:
            self.write(
                "modules/git/module.conf",
                repr(
                    {"schema_version": 1, "name": "git", "facts": {"installed": fact}}
                ),
            )
            with self.subTest(fact=fact), self.assertRaisesRegex(ConfigError, "fact"):
                load_repository(self.repo)

    def test_profile_order_and_duplicate_selection(self):
        other = self.repo / "modules/zsh"
        other.mkdir()
        (other / "module.conf").write_text("{'schema_version': 1, 'name': 'zsh'}")
        self.write(
            "profiles/developer.conf",
            "{'schema_version': 1, 'name': 'developer', 'modules': ['zsh', 'git']}",
        )
        self.assertEqual(
            [m.name for m in load_repository(self.repo, "developer").modules],
            ["zsh", "git"],
        )
        self.write(
            "profiles/developer.conf",
            "{'schema_version': 1, 'name': 'developer', 'modules': ['git', 'git']}",
        )
        with self.assertRaisesRegex(ConfigError, "duplicate"):
            load_repository(self.repo, "developer")

    def test_plugin_declarations_are_data_only(self):
        self.write(
            "defaults.conf",
            "{'schema_version': 1, 'plugins': ['vendor/not-installed']}",
        )
        self.assertEqual(
            load_repository(self.repo).defaults["plugins"], ["vendor/not-installed"]
        )
        for plugins in ["path", [""], ["same", "same"]]:
            self.write("defaults.conf", repr({"schema_version": 1, "plugins": plugins}))
            with self.subTest(plugins=plugins), self.assertRaises(ConfigError):
                load_repository(self.repo)

    def test_provider_opt_in_defaults_and_atomic_replacement(self):
        defaults = {"items": ["a"], "env": {"OLD": "value"}, "quiet": True}
        options = {"items": ["b"], "env": {"NEW": "value"}, "command": "echo"}
        result = compose_defaults(
            "script", defaults, options, ("items", "env", "quiet")
        )
        self.assertEqual(result, dict(options, quiet=True))
        result["items"].append("c")
        self.assertEqual(options["items"], ["b"])
        self.assertEqual(defaults["items"], ["a"])
        with self.assertRaisesRegex(ConfigError, "unsupported default options"):
            compose_defaults("script", {"command": "untrusted default"}, {}, ("quiet",))

    def test_destination_uses_repo_and_preserves_final_symlink(self):
        target = self.repo / "target"
        target.write_text("preserve")
        link = self.repo / "link"
        link.symlink_to(target)
        self.assertEqual(destination("link", self.repo), link.resolve().parent / "link")
        self.assertEqual(
            destination("dir/../new", self.repo), self.repo.resolve() / "new"
        )
        with patch.dict(os.environ, {"HOME": str(self.repo)}):
            self.assertEqual(
                destination("~/.gitconfig", Path("/unrelated")),
                self.repo.resolve() / ".gitconfig",
            )

    def test_nul_paths_are_config_errors(self):
        with self.assertRaises(ConfigError):
            destination("bad\x00path", self.repo)
        with self.assertRaises(ConfigError):
            load_repository(self.repo).modules[0].asset("bad\x00path")
