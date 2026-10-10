"""Installer home expansion is opt-in and never evaluates shell expressions."""

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.providers.contracts import Context
from etchlib.providers.installer.schema import normalize


class InstallerHomeTests(unittest.TestCase):
    def test_expands_only_current_user_prefix_without_mutating_config(self) -> None:
        root = Path.cwd()
        home = root / "home with spaces $literal"
        config: dict[str, Any] = {
            "url": "https://example.test/install",
            "args": [
                "~",
                "~/.local/bin",
                "$HOME/bin",
                "~someone/bin",
                "prefix ~/bin",
                "$(command)",
                "",
            ],
            "env": {"BIN_DIR": "~/bin", "LITERAL": "$HOME/bin"},
        }
        for system in ("Linux", "Windows"):
            with (
                self.subTest(system=system),
                patch("platform.system", return_value=system),
                patch("pathlib.Path.home", return_value=home),
            ):
                context = Context(root, root, "demo", {})
                literal = normalize(config, context)
                self.assertEqual(literal.args, tuple(config["args"]))
                expanded = normalize(dict(config, expand_home=True), context)
                self.assertEqual(
                    expanded.args,
                    (
                        str(home),
                        str(home) + "/.local/bin",
                        "$HOME/bin",
                        "~someone/bin",
                        "prefix ~/bin",
                        "$(command)",
                        "",
                    ),
                )
                self.assertEqual(
                    expanded.options["env"],
                    {"BIN_DIR": str(home) + "/bin", "LITERAL": "$HOME/bin"},
                )
                self.assertEqual(config["env"]["BIN_DIR"], "~/bin")
                native = normalize(
                    dict(config, args=[r"~\bin"], expand_home=True), context
                )
                self.assertEqual(
                    native.args,
                    (str(home) + r"\bin" if system == "Windows" else r"~\bin",),
                )
                inherited = normalize(
                    config,
                    Context(
                        root, root, "demo", {}, {"installer": {"expand_home": True}}
                    ),
                )
                self.assertEqual(inherited.args, expanded.args)
                disabled = normalize(
                    dict(config, expand_home=False),
                    Context(
                        root, root, "demo", {}, {"installer": {"expand_home": True}}
                    ),
                )
                self.assertEqual(disabled.args, literal.args)

    def test_invalid_option_is_rejected(self) -> None:
        context = Context(Path.cwd(), Path.cwd(), "demo", {})
        for invalid in (1, "yes", None):
            with (
                self.subTest(value=invalid),
                self.assertRaisesRegex(ValueError, "expand_home must be boolean"),
            ):
                normalize(
                    {"url": "https://example.test/install", "expand_home": invalid},
                    context,
                )
