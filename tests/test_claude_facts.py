"""Native facts, declared refresh and serialized user plugin installs."""

import ast
import json
import sys
from dataclasses import replace

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.observations import FactRef, FactState
from tests.claude_fixtures import ROOT, ClaudeFixture


class ClaudeFactTests(ClaudeFixture):
    def test_command_version_marketplace_and_user_plugin_facts(self) -> None:
        self.state(
            marketplaces=[self.market()],
            installed=[
                self.plugin(),
                {**self.plugin("project"), "id": "extra@catalog"},
            ],
        )
        config = {"command": str(self.command)}
        context = replace(self.context, inspection_cache={})
        self.assertEqual(
            gather_fact(self.registry.fact("claude.command"), config, context).value,
            str(self.command),
        )
        self.assertEqual(self.calls(), [])
        self.assertEqual(
            gather_fact(self.registry.fact("claude.version"), config, context).value,
            "2.1.312",
        )
        markets = gather_fact(
            self.registry.fact("claude.marketplaces"), config, context
        )
        self.assertEqual(
            markets.value, {"catalog": "https://github.com/owner/repo.git"}
        )
        markets.value.clear()
        self.assertEqual(
            gather_fact(
                self.registry.fact("claude.marketplaces"), config, context
            ).value,
            {"catalog": "https://github.com/owner/repo.git"},
        )
        plugins = gather_fact(self.registry.fact("claude.plugins"), config, context)
        self.assertEqual(plugins.value, ["hello@catalog"])
        plugins.value.append("mutation")
        self.assertEqual(
            gather_fact(self.registry.fact("claude.plugins"), config, context).value,
            ["hello@catalog"],
        )
        self.assertEqual(len(self.calls()), 3)
        self.command.unlink()
        self.assertEqual(
            gather_fact(self.registry.fact("claude.command"), config, context).state,
            FactState.UNAVAILABLE,
        )

    def test_sources_and_non_marketplace_plugins_are_not_confused_with_declared_installs(
        self,
    ) -> None:
        self.state(
            marketplaces=[
                {
                    "name": "pinned",
                    "source": "github",
                    "repo": "owner/repo",
                    "ref": "branch",
                    "installLocation": "/cache/pinned",
                },
                {
                    "name": "ssh",
                    "source": "git",
                    "url": "git@example.com:team/repo.git",
                    "installLocation": "/cache/ssh",
                },
                {
                    "name": "local",
                    "source": "directory",
                    "path": str(self.root),
                    "installLocation": str(self.root),
                },
            ],
            installed=[
                {**self.plugin(), "id": "hello@skills-dir"},
                self.plugin("managed"),
            ],
        )
        config = {"command": str(self.command)}
        self.assertEqual(
            gather_fact(
                self.registry.fact("claude.marketplaces"), config, self.context
            ).value,
            {"pinned": None, "ssh": None, "local": str(self.root)},
        )
        self.assertEqual(
            gather_fact(
                self.registry.fact("claude.plugins"), config, self.context
            ).value,
            [],
        )

    def staged(self) -> None:
        self.module(
            facts={
                "installed": {
                    "provider": "claude.plugins",
                    "config": {"command": str(self.command)},
                }
            },
            actions=[
                {
                    "claude": {
                        "command": str(self.command),
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

    def test_install_refresh_and_second_apply_noop(self) -> None:
        self.staged()
        repo = load_repository(self.root)
        report = apply_repository(repo, self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        fact = report.facts[FactRef("demo", "installed")]
        assert fact is not None
        self.assertEqual(fact.value, ["hello@catalog"])
        self.assertTrue((self.root / "configured").is_dir())
        second = apply_repository(repo, self.registry, jobs=2)
        self.assertTrue(second.succeeded, second.error)
        self.assertTrue(
            all(result.status is Status.SKIPPED for result in second.actions)
        )
        self.assertEqual(len([args for args in self.calls() if "install" in args]), 1)

    def test_failed_producer_blocks_dependent_configuration(self) -> None:
        self.state(fail=["plugin", "install", "hello@catalog", "--scope", "user"])
        self.staged()
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertFalse(report.succeeded)
        self.assertEqual(report.actions[0].status, Status.FAILED)
        self.assertEqual(report.actions[1].status, Status.BLOCKED)
        self.assertFalse((self.root / "configured").exists())

    def test_same_user_plugin_is_installed_once_with_concurrent_modules(self) -> None:
        self.state(gate=True, marketplaces=[self.market()])
        for name in ("a", "b"):
            self.module(
                name,
                actions=[
                    {
                        "claude": {
                            "command": str(self.command),
                            "plugins": ["hello@catalog"],
                        }
                    }
                ],
            )
        script = """import sys,time
from pathlib import Path
root = Path(sys.argv[1])
deadline = time.monotonic() + 5
while not (root / 'started').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('Claude did not start')
    time.sleep(0.005)
(root / 'release').touch()
"""
        self.module(
            "c",
            actions=[
                {"shell": {"command": [sys.executable, "-c", script, str(self.bin)]}}
            ],
        )
        report = apply_repository(load_repository(self.root), self.registry, jobs=3)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(len([args for args in self.calls() if "install" in args]), 1)
        self.assertFalse((self.bin / "install.lock").exists())

    def test_duplicate_rows_and_invalid_json_fail_fact_collection(self) -> None:
        config = {"command": str(self.command)}
        for key, output, kind in (
            ("plugin_output", json.dumps([self.plugin(), self.plugin()]), "plugins"),
            (
                "marketplace_output",
                json.dumps([self.market(), self.market()]),
                "marketplaces",
            ),
            ("plugin_output", "invalid", "plugins"),
        ):
            self.state(**{key: output})
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                gather_fact(self.registry.fact("claude." + kind), config, self.context)
        for path in (ROOT / "plugins/claude").glob("*.py"):
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))
