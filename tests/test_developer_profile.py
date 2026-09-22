"""Prove the eight-module example through the vendored, stdlib-only CLI."""

import json
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.plugins.loader import load_plugins
from tests.developer_fixtures import DeveloperFixture


class DeveloperProfileTests(DeveloperFixture):
    def test_clean_plan_apply_refresh_and_second_apply(self) -> None:
        facts = self.cli("facts")
        self.assertEqual(facts.returncode, 0, facts.stderr)
        self.assertIn("module/starship/version: UNAVAILABLE", facts.stdout)
        plan = self.cli("plan", "-v")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertIn("DEFERRED", plan.stdout)
        self.assertIn("etch-homebrew", plan.stdout)
        self.assertIn("etch-vscode", plan.stdout)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertEqual(self.server.requests, [])
        self.assertFalse(
            self.calls("brew")
            and any(c["args"][0] == "install" for c in self.calls("brew"))
        )
        first = self.cli("apply", "--jobs", "4")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        for path in (
            ".gitconfig",
            ".zshrc",
            ".vimrc",
            ".tmux.conf",
            ".config/starship.toml",
        ):
            self.assertTrue((self.home / path).is_symlink(), path)
        self.assertEqual(len(self.server.requests), 1)
        self.assertIn("modern.conf", str((self.home / ".tmux.conf").resolve()))
        self.assertIn("module/starship/version: VALUE", self.cli("facts").stdout)
        brew_calls = self.calls("brew")
        code_calls = self.calls("code")
        second = self.cli("apply", "--jobs", "4")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(
            [line for line in second.stdout.splitlines() if line.startswith("CHANGED")],
            ["CHANGED zsh:action[1]: Commands ran"],
        )
        self.assertEqual(len(self.server.requests), 1)
        self.assertEqual(
            [c for c in self.calls("brew") if c["args"][0] == "install"],
            [c for c in brew_calls if c["args"][0] == "install"],
        )
        self.assertEqual(
            [c for c in self.calls("code") if c[0] == "--install-extension"],
            [c for c in code_calls if c[0] == "--install-extension"],
        )
        self.assertIn("opaque", self.cli("doctor").stdout)
        self.assertIn("RUN", self.cli("plan").stdout)
        self.assertEqual(self.cli("doctor").returncode, 0)

    def test_old_tmux_selects_legacy_configuration(self) -> None:
        self.tool("tmux", "print('tmux 2.9a')\n")
        result = self.cli("apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("legacy.conf", str((self.home / ".tmux.conf").resolve()))

    def test_platform_font_branches(self) -> None:
        repository = load_repository(self.repo, selected=["fonts"])
        for system, expected, absent in (
            ("Linux", ".local/share/fonts", "Library/Fonts"),
            ("Darwin", "Library/Fonts", ".local/share/fonts"),
        ):
            with (
                self.subTest(system=system),
                patch("platform.system", return_value=system),
            ):
                report = apply_repository(repository, core_registry())
                self.assertTrue(report.succeeded, report.error)
                self.assertTrue((self.home / expected).is_dir())
                self.assertFalse((self.home / absent).exists())
                (self.home / expected).rmdir()

    def test_invalid_plugin_api_stops_before_mutation(self) -> None:
        entry = self.repo / "vendor/etch-vscode/etch_plugin.py"
        entry.write_text(entry.read_text().replace('"api": 1', '"api": 999'))
        result = self.cli("apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("API", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertEqual(self.server.requests, [])

    def test_cycle_stops_before_mutation(self) -> None:
        for name, dependency in (("git", "zsh"), ("zsh", "git")):
            config = self.module_config(name)
            config["requires"] = [dependency]
            self.write_module(name, config)
        result = self.cli("apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cycle", result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertEqual(self.server.requests, [])

    def test_claim_conflict_after_starship_refresh(self) -> None:
        # The later claim is invisible until the installer produces the version.
        config = self.module_config("starship")
        config["actions"][1]["link"] = {
            "~/.gitconfig": {
                "path": "files/starship.toml",
                "create": True,
                "relink": True,
            }
        }
        self.write_module("starship", config)
        repository = load_repository(self.repo, "developer")
        registry = load_plugins(
            self.repo, repository.defaults["plugins"], core_registry()
        ).registry
        result = apply_repository(repository, registry)
        self.assertFalse(result.succeeded)
        self.assertIn("destination conflict", result.error or "")
        self.assertEqual(len(self.server.requests), 1)
        self.assertIn("git/files/gitconfig", str((self.home / ".gitconfig").resolve()))
        self.assertFalse((self.home / ".config/starship.toml").exists())
        self.assertTrue(
            any(
                r.node.module == "starship"
                and r.node.index == 1
                and r.status is Status.BLOCKED
                for r in result.actions
            )
        )

    def test_homebrew_installations_are_serialized_across_modules(self) -> None:
        # Hold the first install until independent work releases it. A second
        # simultaneous invocation fails the fake CLI's exclusive install lock.
        state_path = self.root / "brew/state.json"
        state_path.write_text(json.dumps({"formula": [], "cask": [], "gate": True}))
        fonts = self.module_config("fonts")
        fonts["actions"].insert(0, {"brew": {"formulae": ["fontconfig"]}})
        self.write_module("fonts", fonts)
        zsh = self.module_config("zsh")
        program = (
            "from pathlib import Path; import time; p=Path({!r}); deadline=time.monotonic()+5\n"
            "while not (p/'started').exists():\n if time.monotonic()>deadline: raise SystemExit('install did not start')\n time.sleep(.01)\n"
            "(p/'release').touch()\n"
        ).format(str(self.root / "brew"))
        zsh["actions"].append({"shell": {"command": [self.python, "-c", program]}})
        self.write_module("zsh", zsh)
        result = self.cli("apply", "--jobs", "4")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installs = [
            call["args"] for call in self.calls("brew") if call["args"][0] == "install"
        ]
        self.assertEqual(len(installs), 2)
        self.assertTrue((self.root / "brew/release").exists())
