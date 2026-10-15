"""Native marketplace/plugin reconciliation and failure boundaries."""

from typing import Any

from etchlib.core import core_registry
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import apply_action
from etchlib.providers.plans import PlanStatus
from tests.codex_fixtures import CodexFixture


class CodexActionTests(CodexFixture):
    def test_optional_registration_and_validation_before_cli_calls(self) -> None:
        with self.assertRaises(ProviderError):
            core_registry().action("codex")
        config: dict[str, Any]
        for config in (
            {"plugins": ["--flag"]},
            {"plugins": ["a@b@c"]},
            {"marketplaces": ["https://user:password@example.com/repo.git"]},
            {"marketplaces": ["--flag"]},
            {"remove": []},
            {"timeout": False},
        ):
            with self.subTest(config=config), self.assertRaises(ProviderError):
                self.codex_plan(**config)
        self.assertEqual(self.calls(), [])

    def test_marketplace_source_is_not_its_registered_name(self) -> None:
        self.state(
            marketplaces=[
                {
                    "name": "different-name",
                    "marketplaceSource": {
                        "sourceType": "git",
                        "source": "https://github.com/owner/repo.git",
                    },
                }
            ]
        )
        plan = self.codex_plan(marketplaces=["owner/repo"])
        self.assertEqual(plan.status, PlanStatus.SKIP)
        self.assertFalse(any("add" in call for call in self.calls()))

    def test_marketplaces_are_added_before_plugins_and_second_apply_is_noop(
        self,
    ) -> None:
        plan = self.codex_plan(marketplaces=["owner/repo"], plugins=["hello@catalog"])
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertEqual(plan.resources, ("application:codex",))
        self.assertEqual(len(self.calls()), 2)
        result = apply_action(self.entry, plan, self.context)
        self.assertTrue(result.changed)
        mutations = [call for call in self.calls() if "add" in call]
        self.assertEqual(
            mutations,
            [
                [
                    "plugin",
                    "marketplace",
                    "add",
                    "https://github.com/owner/repo.git",
                    "--json",
                ],
                ["plugin", "add", "hello@catalog", "--json"],
            ],
        )
        self.assertEqual(
            self.codex_plan(
                marketplaces=["owner/repo"], plugins=["hello@catalog"]
            ).status,
            PlanStatus.SKIP,
        )
        self.assertFalse(apply_action(self.entry, plan, self.context).changed)

    def test_available_is_not_installed_and_disabled_installs_are_preserved(
        self,
    ) -> None:
        disabled = {
            "pluginId": "hello@catalog",
            "name": "hello",
            "marketplaceName": "catalog",
            "installed": True,
            "enabled": False,
            "version": "99.0.0",
        }
        self.state(
            installed=[disabled],
            available=[
                dict(disabled, installed=False, pluginId="other@catalog", name="other")
            ],
        )
        self.assertEqual(
            self.codex_plan(plugins=["hello@catalog"]).status, PlanStatus.SKIP
        )
        plan = self.codex_plan(plugins=["other@catalog"])
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertEqual(self.current()["installed"], [disabled])

    def test_partial_failure_and_reapply_preserve_installed_extras(self) -> None:
        extra = {
            "pluginId": "extra@catalog",
            "name": "extra",
            "marketplaceName": "catalog",
            "installed": True,
            "enabled": True,
            "version": "99",
        }
        self.state(
            marketplaces=[{"name": "catalog"}],
            installed=[extra],
            fail=["plugin", "add", "zzz@catalog", "--json"],
        )
        plan = self.codex_plan(plugins=["aaa@catalog", "zzz@catalog"])
        with self.assertRaisesRegex(ProviderError, "controlled CLI failure"):
            apply_action(self.entry, plan, self.context)
        state = self.current()
        self.assertEqual(len(state["installed"]), 2)
        state.pop("fail")
        self.state(**state)
        apply_action(
            self.entry,
            self.codex_plan(plugins=["aaa@catalog", "zzz@catalog"]),
            self.context,
        )
        self.assertEqual(
            [call[2] for call in self.calls() if call[:2] == ["plugin", "add"]],
            ["aaa@catalog", "zzz@catalog", "zzz@catalog"],
        )
        self.assertIn(extra, self.current()["installed"])

    def test_success_without_presence_is_failure(self) -> None:
        self.state(marketplaces=[{"name": "catalog"}], pretend=True)
        with self.assertRaisesRegex(ProviderError, "remains missing"):
            apply_action(
                self.entry, self.codex_plan(plugins=["hello@catalog"]), self.context
            )

    def test_invalid_inventory_and_missing_cli_fail_explicitly(self) -> None:
        for output in (
            "not json",
            "{}",
            '{"installed": {}}',
            '{"installed":[{"pluginId":"a@b","installed":false}]}',
        ):
            self.state(plugin_output=output)
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.codex_plan(plugins=["hello@catalog"])
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.codex_plan(command="/not/an/executable")

    def test_source_aliases_and_unrelated_unsupported_sources_are_preserved(
        self,
    ) -> None:
        local = str((self.context.module_root / "catalog").resolve())
        rows = [
            {
                "name": "local",
                "marketplaceSource": {"sourceType": "local", "source": local},
            },
            {
                "name": "custom",
                "marketplaceSource": {
                    "sourceType": "git",
                    "source": "https://example.com/repositories/plugins",
                },
            },
            {
                "name": "ssh-extra",
                "marketplaceSource": {
                    "sourceType": "git",
                    "source": "git@example.com:team/plugins.git",
                },
            },
        ]
        self.state(marketplaces=rows)
        plan = self.codex_plan(
            marketplaces=["./catalog", "https://example.com/repositories/plugins"]
        )
        self.assertEqual(plan.status, PlanStatus.SKIP)
        self.assertEqual(self.current()["marketplaces"], rows)

    def test_malformed_marketplace_inventory_is_not_an_empty_inventory(self) -> None:
        for output in (
            "{}",
            '{"marketplaces":{}}',
            '{"marketplaces":[{"name":"same"},{"name":"same"}]}',
            '{"marketplaces":[{"name":"catalog","marketplaceSource":{}}]}',
        ):
            self.state(marketplace_output=output)
            with self.subTest(output=output), self.assertRaises(ProviderError):
                self.codex_plan(marketplaces=["owner/repo"])
        self.assertFalse(any("add" in call for call in self.calls()))

    def test_native_source_collision_is_not_repaired_by_replacing_user_state(
        self,
    ) -> None:
        existing = {
            "name": "catalog",
            "marketplaceSource": {
                "sourceType": "git",
                "source": "https://github.com/other/repo.git",
            },
        }
        self.state(marketplaces=[existing])
        with self.assertRaisesRegex(ProviderError, "different source"):
            apply_action(
                self.entry,
                self.codex_plan(marketplaces=["owner/repo"], plugins=["hello@catalog"]),
                self.context,
            )
        self.assertEqual(self.current()["marketplaces"], [existing])
        self.assertFalse(
            any(
                call[:2] == ["plugin", "add"] or "remove" in call or "upgrade" in call
                for call in self.calls()
            )
        )
