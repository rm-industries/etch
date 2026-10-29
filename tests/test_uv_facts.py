"""User tool facts, executable refresh and serialized reconciliation."""

import ast
import sys
from dataclasses import replace

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.facts.repository import repository_facts
from etchlib.providers.lifecycle import apply_action, gather_fact
from etchlib.providers.observations import FactRef, FactState
from tests.uv_fixtures import ROOT, UvFixture


class UvFactTests(UvFixture):
    def test_command_version_and_detached_tool_inventory(self) -> None:
        self.state(tools={"tool": "1", "other": "2"})
        config = {"command": str(self.command)}
        context = replace(self.context, inspection_cache={})
        self.assertEqual(
            gather_fact(self.registry.fact("uv.command"), config, context).value,
            str(self.command),
        )
        self.assertEqual(self.calls(), [])
        self.assertEqual(
            gather_fact(self.registry.fact("uv.version"), config, context).value,
            "0.12.17",
        )
        tools = gather_fact(self.registry.fact("uv.tools"), config, context)
        self.assertEqual(tools.value, ["other", "tool"])
        tools.value.append("mutation")
        self.assertEqual(
            gather_fact(self.registry.fact("uv.tools"), config, context).value,
            ["other", "tool"],
        )
        self.assertEqual(len(self.calls()), 4)
        self.command.unlink()
        self.assertEqual(
            gather_fact(self.registry.fact("uv.command"), config, context).state,
            FactState.UNAVAILABLE,
        )

    def test_warning_inventory_is_error_not_unavailable_or_empty(self) -> None:
        self.state(warning="warning: tool environment not found")
        self.module(
            facts={"tools": {"provider": "uv.tools", "command": str(self.command)}}
        )
        store = repository_facts(load_repository(self.root), self.registry)
        self.assertEqual(store.get(FactRef("demo", "tools")).state, FactState.ERROR)

    def staged(self) -> None:
        executable = str(self.bin / "executables/installed-tool")
        self.module(
            facts={
                "tools": {"provider": "uv.tools", "command": str(self.command)},
                "tool": {"provider": "command", "config": executable},
                "version": {
                    "provider": "version",
                    "command": [executable, "--version"],
                },
            },
            actions=[
                {
                    "uv": {"command": str(self.command), "tools": ["tool"]},
                    "refresh": ["tools", "tool", "version"],
                },
                {
                    "create": ["tools-ready"],
                    "when": {"fact": {"name": "tools", "equals": ["tool"]}},
                },
                {
                    "create": ["command-ready"],
                    "when": {"fact": {"name": "tool", "equals": True}},
                },
                {
                    "create": ["version-ready"],
                    "when": {"fact": {"name": "version", "matches": ">=2"}},
                },
            ],
        )

    def test_install_refresh_exposed_executable_then_noop(self) -> None:
        self.state(produce=True)
        self.staged()
        repo = load_repository(self.root)
        report = apply_repository(repo, self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        for path in ("tools-ready", "command-ready", "version-ready"):
            self.assertTrue((self.root / path).is_dir())
        fact = report.facts[FactRef("demo", "tools")]
        assert fact is not None
        self.assertEqual(fact.value, ["tool"])
        second = apply_repository(repo, self.registry, jobs=2)
        self.assertTrue(second.succeeded, second.error)
        self.assertTrue(
            all(result.status is Status.SKIPPED for result in second.actions)
        )
        self.assertEqual(self.installs(), [["tool>=0"]])

    def test_failed_install_blocks_configuration_and_refresh(self) -> None:
        self.state(fail_tool="tool")
        self.staged()
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertFalse(report.succeeded)
        self.assertEqual(report.actions[0].status, Status.FAILED)
        self.assertTrue(
            all(result.status is Status.BLOCKED for result in report.actions[1:])
        )
        self.assertFalse((self.root / "tools-ready").exists())

    def test_parallel_requests_serialize_installs_and_allow_unrelated_work(
        self,
    ) -> None:
        self.state(gate=True)
        for name in ("a", "b"):
            self.module(
                name,
                actions=[{"uv": {"command": str(self.command), "tools": ["tool"]}}],
            )
        script = """import sys,time
from pathlib import Path
root = Path(sys.argv[1])
deadline = time.monotonic() + 5
while not (root / 'started').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('uv did not start')
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
        self.assertEqual(self.installs(), [["tool>=0"]])
        self.assertFalse((self.bin / "install.lock").exists())

    def test_later_requests_reconcile_tools_appearing_during_prior_install(
        self,
    ) -> None:
        self.state(appeared=["b"])
        self.assertTrue(
            apply_action(
                self.entry, self.uv_plan(tools=["a", "b"]), self.context
            ).changed
        )
        self.assertEqual(self.installs(), [["a>=0"]])
        for path in (ROOT / "plugins/uv").glob("*.py"):
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))
