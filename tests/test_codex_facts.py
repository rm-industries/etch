"""Native Codex inventories are facts only after explicit plugin registration."""

import ast
from dataclasses import replace
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.providers.lifecycle import gather_fact, plan_action
from etchlib.providers.observations import FactRef, FactState
from tests.codex_fixtures import ROOT, CodexFixture


class CodexFactTests(CodexFixture):
    def test_facts_report_registered_sources_and_installed_ids(self) -> None:
        self.state(
            marketplaces=[
                {
                    "name": "actual-name",
                    "marketplaceSource": {
                        "sourceType": "git",
                        "source": "https://github.com/owner/repo.git",
                    },
                }
            ],
            installed=[
                {
                    "pluginId": "hello@actual-name",
                    "name": "hello",
                    "marketplaceName": "actual-name",
                    "installed": True,
                    "enabled": False,
                }
            ],
        )
        config = {"command": str(self.code)}
        self.assertEqual(
            gather_fact(
                self.registry.fact("codex.command"), config, self.context
            ).value,
            str(self.code),
        )
        self.assertEqual(
            gather_fact(
                self.registry.fact("codex.marketplaces"), config, self.context
            ).value,
            {"actual-name": "https://github.com/owner/repo.git"},
        )
        self.assertEqual(
            gather_fact(
                self.registry.fact("codex.plugins"), config, self.context
            ).value,
            ["hello@actual-name"],
        )
        self.assertEqual(
            gather_fact(
                self.registry.fact("codex.version"), config, self.context
            ).state,
            FactState.VALUE,
        )
        missing = gather_fact(
            self.registry.fact("codex.command"),
            {"command": "/not/present"},
            self.context,
        )
        self.assertEqual(missing.state, FactState.UNAVAILABLE)

    def test_defaults_are_action_only_and_explicit_overrides_win(self) -> None:
        context = replace(
            self.context, defaults={"codex": {"command": str(self.code), "timeout": 10}}
        )
        self.assertEqual(
            plan_action(self.entry, {"plugins": []}, context).payload.target.timeout, 10
        )
        self.assertEqual(
            plan_action(self.entry, {"timeout": 5}, context).payload.target.timeout, 5
        )

    def test_registered_consumer_refreshes_fact_after_install(self) -> None:
        self.module(
            facts={
                "installed": {
                    "provider": "codex.plugins",
                    "config": {"command": str(self.code)},
                }
            },
            actions=[
                {
                    "codex": {
                        "command": str(self.code),
                        "marketplaces": ["owner/repo"],
                        "plugins": ["hello@catalog"],
                    },
                    "refresh": ["installed"],
                },
                {
                    "create": ["configured"],
                    "when": {
                        "fact": {"name": "installed", "equals": ["hello@catalog"]}
                    },
                },
            ],
        )
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertTrue((self.root / "configured").exists())
        observed = report.facts[FactRef("demo", "installed")]
        assert observed is not None
        self.assertEqual(observed.value, ["hello@catalog"])

    def test_timeout_output_bound_and_python39_stdlib_contract(self) -> None:
        self.state(sleep=1)
        with self.assertRaisesRegex(ValueError, "timed out"):
            self.codex_plan(plugins=["hello@catalog"], timeout=0.02)
        module = __import__(
            type(self.entry.provider).__module__.rsplit(".", 1)[0] + ".cli",
            fromlist=["run"],
        )
        self.state(marketplace_output="x" * 100)
        with (
            patch.object(module, "OUTPUT_LIMIT", 64),
            self.assertRaisesRegex(ValueError, "exceeds"),
        ):
            self.codex_plan(marketplaces=["owner/repo"])
        allowed = {
            "dataclasses",
            "json",
            "math",
            "os",
            "pathlib",
            "re",
            "shutil",
            "subprocess",
            "tempfile",
            "typing",
            "urllib",
            "etchlib",
        }
        for file in (ROOT / "plugins/codex").glob("*.py"):
            tree = ast.parse(file.read_text(), feature_version=(3, 9))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split(".")[0], allowed)
                elif (
                    isinstance(node, ast.ImportFrom) and not node.level and node.module
                ):
                    self.assertIn(node.module.split(".")[0], allowed)

    def test_windows_batch_wrappers_do_not_reach_subprocess(self) -> None:
        import importlib

        module = importlib.import_module(
            type(self.entry.provider).__module__.rsplit(".", 1)[0] + ".cli"
        )
        options = self.codex_plan().payload.target
        with (
            patch.object(module.os, "name", "nt"),
            patch.object(module.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "native codex.exe"):
                module.run(
                    "codex.cmd", options, ("plugin", "list", "--json"), self.context
                )
        run.assert_not_called()
