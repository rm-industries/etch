"""Native user plugin reconciliation without changing versions or enabled state."""

from dataclasses import replace
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers import native
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action, plan_action
from etchlib.providers.plans import PlanStatus
from tests.claude_fixtures import ClaudeFixture


class ClaudeActionTests(ClaudeFixture):
    def test_registration_and_inspection_only_plan(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("claude")
        self.module(
            actions=[
                {
                    "claude": {
                        "command": str(self.command),
                        "marketplaces": ["owner/repo"],
                        "plugins": ["hello@catalog"],
                    }
                }
            ]
        )
        status, output, error = self.cli("-v")
        self.assertEqual(status, 0, error)
        self.assertIn("plugin etch-claude 0.1.0", output)
        self.assertIn("application:claude", output)
        self.assertEqual(
            self.calls(),
            [["plugin", "marketplace", "list", "--json"], ["plugin", "list", "--json"]],
        )
        self.assertEqual(self.current(), {})

    def test_marketplace_before_plugins_with_fresh_verification_and_idempotence(
        self,
    ) -> None:
        plan = self.claude_plan(
            marketplaces=["owner/repo"],
            plugins=["z@catalog", "hello@catalog", "hello@catalog"],
        )
        self.assertEqual(plan.resources, ("application:claude",))
        self.assertTrue(plan.network)
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        mutations = [
            args for args in self.calls() if "add" in args or "install" in args
        ]
        self.assertEqual(
            mutations,
            [
                [
                    "plugin",
                    "marketplace",
                    "add",
                    "https://github.com/owner/repo.git",
                    "--scope",
                    "user",
                ],
                ["plugin", "install", "hello@catalog", "--scope", "user"],
                ["plugin", "install", "z@catalog", "--scope", "user"],
            ],
        )
        second = self.claude_plan(
            marketplaces=["owner/repo"], plugins=["hello@catalog", "z@catalog"]
        )
        self.assertEqual(second.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, second, self.context).changed)

    def test_existing_disabled_user_install_and_extras_are_preserved(self) -> None:
        rows = [
            self.plugin(),
            {**self.plugin(), "id": "extra@catalog", "enabled": True},
        ]
        self.state(marketplaces=[self.market()], installed=rows)
        plan = self.claude_plan(marketplaces=["owner/repo"], plugins=["hello@catalog"])
        self.assertEqual(plan.status, PlanStatus.SKIP)
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(self.current()["installed"], rows)

    def test_project_install_does_not_satisfy_user_presence(self) -> None:
        project = self.plugin(scope="project")
        self.state(marketplaces=[self.market()], installed=[project])
        plan = self.claude_plan(plugins=["hello@catalog"])
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertEqual(self.current()["installed"][0], project)
        self.assertEqual(len(self.current()["installed"]), 2)

    def test_partial_failure_preserves_prior_install_for_reapply(self) -> None:
        self.state(fail=["plugin", "install", "z@catalog", "--scope", "user"])
        with self.assertRaisesRegex(ProviderError, "status 7"):
            apply_action(
                self.entry,
                self.claude_plan(
                    marketplaces=["owner/repo"], plugins=["hello@catalog", "z@catalog"]
                ),
                self.context,
            )
        current = self.current()
        current.pop("fail")
        self.state(**current)
        apply_action(
            self.entry,
            self.claude_plan(
                marketplaces=["owner/repo"], plugins=["hello@catalog", "z@catalog"]
            ),
            self.context,
        )
        self.assertEqual(
            [args[2] for args in self.calls() if args[:2] == ["plugin", "install"]],
            ["hello@catalog", "z@catalog", "z@catalog"],
        )

    def test_validation_rejects_flags_refs_urls_and_unknown_options_before_probing(
        self,
    ) -> None:
        for config in (
            {"plugins": ["--help"]},
            {"plugins": ["a@b@c"]},
            {"plugins": ["../a@b"]},
            {"plugins": ["hello@skills-dir"]},
            {"plugins": "hello@catalog"},
            {"marketplaces": ["--help"]},
            {"marketplaces": ["owner/repo#branch"]},
            {"marketplaces": ["https://user:password@example.com/repo.git"]},
            {"marketplaces": ["https://example.com/catalog.json"]},
            {"marketplaces": ["http://example.com/repo.git"]},
            {"scope": "project"},
            {"timeout": True},
            {"timeout": float("inf")},
            {"command": "\n"},
        ):
            with self.subTest(config=config), self.assertRaises(ProviderError):
                self.claude_plan(**config)
        self.assertEqual(self.calls(), [])

    def test_missing_cli_defaults_and_executable_drift(self) -> None:
        context = replace(
            self.context,
            defaults={"claude": {"command": str(self.command), "timeout": 10}},
        )
        plan = plan_action(self.entry, {"plugins": ["hello@catalog"]}, context)
        self.assertEqual(plan.payload.target.timeout, 10)
        self.command.unlink()
        with self.assertRaisesRegex(ProviderError, "executable changed"):
            apply_action(self.entry, plan, context)
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.claude_plan(plugins=["hello@catalog"])

    def test_apply_rechecks_native_state_in_both_directions(self) -> None:
        plan = self.claude_plan(plugins=["hello@catalog"])
        self.state(marketplaces=[self.market()], installed=[self.plugin()])
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)
        satisfied = self.claude_plan(plugins=["hello@catalog"])
        self.state(marketplaces=[self.market()])
        self.assertTrue(apply_action(self.entry, satisfied, self.context).changed)

    def test_false_success_and_source_collisions_fail_without_replacement(self) -> None:
        self.state(pretend_market=True)
        with self.assertRaisesRegex(ProviderError, "remains missing"):
            apply_action(
                self.entry, self.claude_plan(marketplaces=["owner/repo"]), self.context
            )
        self.state(marketplaces=[self.market()], pretend=True)
        with self.assertRaisesRegex(ProviderError, "remains missing"):
            apply_action(
                self.entry, self.claude_plan(plugins=["hello@catalog"]), self.context
            )
        self.state(marketplaces=[{**self.market(), "repo": "other/repo"}])
        with self.assertRaisesRegex(ProviderError, "different source"):
            apply_action(
                self.entry, self.claude_plan(marketplaces=["owner/repo"]), self.context
            )
        self.assertEqual(self.current()["marketplaces"][0]["repo"], "other/repo")

    def test_inventory_shapes_and_scope_are_validated(self) -> None:
        for key, output in (
            ("plugin_output", "{}"),
            ("plugin_output", "not json"),
            ("plugin_output", '[{"id":"hello@catalog","scope":"user","enabled":true}]'),
            (
                "plugin_output",
                '[{"id":"hello@catalog","version":"1","scope":"unexpected","enabled":true,"installPath":"/cache"}]',
            ),
            ("marketplace_output", "{}"),
            ("marketplace_output", '[{"name":"catalog"}]'),
            ("marketplace_output", '[{"name":"catalog","source":"github"}]'),
        ):
            self.state(**{key: output})
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.claude_plan(marketplaces=["owner/repo"], plugins=["hello@catalog"])

    def test_timeout_and_shared_output_limit(self) -> None:
        self.state(sleep=1)
        with self.assertRaisesRegex(ProviderError, "timed out"):
            self.claude_plan(plugins=["hello@catalog"], timeout=0.02)
        self.state(plugin_output="x" * 100)
        with patch.object(native, "OUTPUT_LIMIT", 64):
            with self.assertRaisesRegex(ProviderError, "output exceeds"):
                self.claude_plan(plugins=["hello@catalog"])

    def test_marketplace_dependency_installs_are_observed_before_plugin_install(
        self,
    ) -> None:
        self.state(installed_by_marketplace=[self.plugin()])
        plan = self.claude_plan(marketplaces=["owner/repo"], plugins=["hello@catalog"])
        self.assertTrue(apply_action(self.entry, plan, self.context).changed)
        self.assertFalse(
            any(args[:2] == ["plugin", "install"] for args in self.calls())
        )
        self.assertFalse(self.current()["installed"][0]["enabled"])
