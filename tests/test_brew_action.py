import os
from dataclasses import replace
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.brew_fixtures import BrewFixture


class BrewActionTests(BrewFixture):
    def test_external_origin_and_inspection_only_plan(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("brew")
        self.module(
            actions=[{"brew": {"command": str(self.brew), "formulae": ["git"]}}]
        )
        status, output, error = self.cli("-v")
        self.assertEqual(status, 0, error)
        self.assertIn("plugin etch-homebrew 0.1.0", output)
        self.assertIn("package-manager:brew", output)
        self.assertTrue(all(call["args"][0] == "list" for call in self.calls()))

    def test_deterministic_batches_and_idempotence(self) -> None:
        self.state(
            formula=["homebrew/core/git", "unlisted"], cask=["homebrew/cask/firefox"]
        )
        plan = self.brew_plan(
            formulae=["Zsh", "git", "homebrew/core/zsh", "tmux"],
            casks=["firefox", "visual-studio-code"],
        )
        self.assertTrue(plan.network)
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(
            [call["args"] for call in self.calls() if call["args"][0] == "install"],
            [
                ["install", "--formula", "tmux", "zsh"],
                ["install", "--cask", "visual-studio-code"],
            ],
        )
        self.assertIn("unlisted", self.current()["formula"])
        self.assertEqual(
            self.brew_plan(
                formulae=["git", "tmux", "zsh"], casks=["firefox", "visual-studio-code"]
            ).status,
            PlanStatus.SKIP,
        )

    def test_custom_tap_identity_is_not_confused_with_core(self) -> None:
        self.state(formula=["vendor/tap/git"], cask=[])
        plan = self.brew_plan(formulae=["git", "vendor/tap/git"])
        apply_action(self.entry, plan, self.context)
        self.assertEqual(
            [call["args"] for call in self.calls() if call["args"][0] == "install"],
            [["install", "--formula", "git"]],
        )

    def test_no_upgrade_or_cleanup_environment_is_local_to_child(self) -> None:
        with patch.dict(os.environ, {"HOMEBREW_NO_INSTALL_UPGRADE": "0"}):
            apply_action(self.entry, self.brew_plan(formulae=["git"]), self.context)
            self.assertEqual(os.environ["HOMEBREW_NO_INSTALL_UPGRADE"], "0")
        for call in self.calls():
            for name in (
                "HOMEBREW_NO_AUTO_UPDATE",
                "HOMEBREW_NO_INSTALL_UPGRADE",
                "HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK",
                "HOMEBREW_NO_INSTALL_CLEANUP",
            ):
                self.assertEqual(call["env"][name], "1")

    def test_apply_rechecks_packages_installed_after_planning(self) -> None:
        plan = self.brew_plan(formulae=["git"])
        self.state(formula=["git"], cask=[])
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        self.assertFalse(any(call["args"][0] == "install" for call in self.calls()))

    def test_missing_brew_and_defaults_lookup(self) -> None:
        context = replace(self.context, defaults={"brew": {"command": str(self.brew)}})
        self.assertEqual(
            plan_action(self.entry, {"formulae": []}, context).status, PlanStatus.SKIP
        )
        self.brew.unlink()
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.brew_plan(formulae=["git"])

    def test_failure_preserves_prior_success_and_stops_without_retry(self) -> None:
        self.state(formula=[], cask=[], fail_kind="cask")
        with self.assertRaisesRegex(ProviderError, "status 8"):
            apply_action(
                self.entry,
                self.brew_plan(formulae=["git"], casks=["firefox"]),
                self.context,
            )
        self.assertIn("git", self.current()["formula"])
        self.assertEqual(
            len([call for call in self.calls() if call["args"][0] == "install"]), 2
        )

    def test_zero_exit_without_install_is_rejected(self) -> None:
        self.state(formula=[], cask=[], pretend=True)
        with self.assertRaisesRegex(ProviderError, "remain missing"):
            apply_action(self.entry, self.brew_plan(formulae=["git"]), self.context)

    def test_invalid_payloads_and_names_fail_without_probes(self) -> None:
        for name in (
            "--help",
            "./file.rb",
            "https://example.org/pkg",
            "../escape",
            "a/b",
            "file.rb",
            "space name",
        ):
            with self.subTest(name=name), self.assertRaises(ProviderError):
                self.brew_plan(formulae=[name])
        with self.assertRaisesRegex(ProviderError, "upgrades/removal"):
            self.brew_plan(formulae=[], upgrade=True)
        with self.assertRaises(ProviderError):
            self.brew_plan(formulae="git")
        self.assertEqual(self.calls(), [])

    def test_malformed_inventory_failure_and_timeout(self) -> None:
        self.state(output="not a package")
        with self.assertRaises(ProviderError):
            self.brew_plan(formulae=["git"])
        self.state(fail="list")
        with self.assertRaisesRegex(ProviderError, "status 7"):
            self.brew_plan(formulae=["git"])
        self.state(sleep=1)
        with self.assertRaisesRegex(ProviderError, "timed out"):
            self.brew_plan(formulae=["git"], timeout=0.02)

    def test_formula_only_request_does_not_query_casks(self) -> None:
        self.brew_plan(formulae=["git"])
        self.assertEqual(
            [call["args"] for call in self.calls()],
            [["list", "--formula", "--full-name", "-1"]],
        )
