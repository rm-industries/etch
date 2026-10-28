"""Native facts, refresh/dependencies and resource serialization."""

import ast
import subprocess
import sys
from dataclasses import replace

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.facts.repository import repository_facts
from etchlib.providers.lifecycle import gather_fact
from etchlib.providers.observations import FactRef, FactState
from tests.npm_fixtures import ROOT, NpmFixture


class NpmFactTests(NpmFixture):
    def test_command_version_inventory_and_unavailable_facts(self) -> None:
        self.state(packages={"tool": "1", "@scope/tool": "2"})
        config = {"command": str(self.npm)}
        context = replace(self.context, inspection_cache={})
        self.assertEqual(
            gather_fact(self.registry.fact("npm.command"), config, context).value,
            str(self.npm),
        )
        self.assertEqual(self.calls(), [])
        self.assertEqual(
            gather_fact(self.registry.fact("npm.version"), config, context).value,
            "11.19.1",
        )
        result = gather_fact(self.registry.fact("npm.packages"), config, context)
        self.assertEqual(result.value, ["@scope/tool", "tool"])
        result.value.append("mutated")
        self.assertEqual(
            gather_fact(self.registry.fact("npm.packages"), config, context).value,
            ["@scope/tool", "tool"],
        )
        self.assertEqual(len(self.calls()), 3)
        self.npm.unlink()
        self.assertEqual(
            gather_fact(self.registry.fact("npm.command"), config, context).state,
            FactState.UNAVAILABLE,
        )

    def test_bad_inventory_is_an_error_fact(self) -> None:
        self.state(output="not json")
        self.module(
            facts={"packages": {"provider": "npm.packages", "command": str(self.npm)}}
        )
        store = repository_facts(load_repository(self.root), self.registry)
        self.assertEqual(store.get(FactRef("demo", "packages")).state, FactState.ERROR)

    def staged(self) -> None:
        tool = str(self.bin / "installed-tool")
        self.module(
            facts={
                "packages": {"provider": "npm.packages", "command": str(self.npm)},
                "tool": {"provider": "command", "config": tool},
                "version": {"provider": "version", "command": [tool, "--version"]},
            },
            actions=[
                {
                    "npm": {"command": str(self.npm), "packages": ["tool"]},
                    "refresh": ["packages", "tool", "version"],
                },
                {
                    "create": ["configured"],
                    "when": {"fact": {"name": "version", "matches": ">=2"}},
                },
                {
                    "create": ["packages-configured"],
                    "when": {"fact": {"name": "packages", "equals": ["tool"]}},
                },
            ],
        )

    def test_install_refresh_and_second_engine_apply_is_noop(self) -> None:
        self.state(produce=True)
        self.staged()
        repo = load_repository(self.root)
        report = apply_repository(repo, self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertTrue((self.root / "configured").is_dir())
        fact = report.facts[FactRef("demo", "packages")]
        assert fact is not None
        self.assertEqual(fact.value, ["tool"])
        second = apply_repository(repo, self.registry, jobs=2)
        self.assertTrue(second.succeeded, second.error)
        self.assertTrue(
            all(result.status is Status.SKIPPED for result in second.actions)
        )
        self.assertEqual(self.installs(), [["tool"]])

    def test_failed_install_blocks_deferred_configuration(self) -> None:
        self.state(partial_failure=True)
        self.staged()
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertFalse(report.succeeded)
        self.assertEqual(report.actions[0].status, Status.FAILED)
        self.assertEqual(report.actions[1].status, Status.BLOCKED)
        self.assertFalse((self.root / "configured").exists())

    def test_concurrent_modules_serialize_mutation_and_allow_unrelated_progress(
        self,
    ) -> None:
        self.state(gate=True)
        for name in ("a", "b"):
            self.module(
                name,
                actions=[{"npm": {"command": str(self.npm), "packages": ["tool"]}}],
            )
        script = """import sys,time
from pathlib import Path
root = Path(sys.argv[1])
deadline = time.monotonic() + 5
while not (root / 'started').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('npm did not start')
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
        self.assertEqual(self.installs(), [["tool"]])
        self.assertFalse((self.bin / "install.lock").exists())

    def test_dependency_install_can_satisfy_later_request(self) -> None:
        self.state(dependencies=["other"])
        self.module(
            "a", actions=[{"npm": {"command": str(self.npm), "packages": ["tool"]}}]
        )
        self.module(
            "b",
            requires=["a"],
            actions=[{"npm": {"command": str(self.npm), "packages": ["other"]}}],
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.installs(), [["tool"]])

    def test_isolated_runtime_and_python39_grammar(self) -> None:
        self.module(actions=[{"npm": {"command": str(self.npm), "packages": ["tool"]}}])
        script = "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')"
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                script,
                str(ROOT),
                str(ROOT / "etch"),
                "apply",
                "--repo",
                str(self.root),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in [
            ROOT / "etchlib/providers/native.py",
            *(ROOT / "plugins/npm").glob("*.py"),
        ]:
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))
