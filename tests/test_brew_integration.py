import ast
import subprocess
import sys

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from etchlib.facts.repository import repository_facts
from etchlib.providers.observations import FactRef, FactState
from tests.brew_fixtures import ROOT, BrewFixture


class BrewIntegrationTests(BrewFixture):
    def test_presence_version_and_inventory_facts(self) -> None:
        self.state(
            formula=["homebrew/core/git", "git", "vendor/tap/tool"],
            cask=["homebrew/cask/firefox"],
        )
        self.module(
            facts={
                name: {"brew." + name: {"command": str(self.brew)}}
                for name in ("command", "version", "formulae", "casks")
            }
        )
        store = repository_facts(load_repository(self.root), self.registry)
        self.assertEqual(store.get(FactRef("demo", "command")).value, str(self.brew))
        self.assertEqual(self.calls(), [])
        self.assertEqual(store.get(FactRef("demo", "version")).value, "5.0.0")
        self.assertEqual(
            store.get(FactRef("demo", "formulae")).value, ["git", "vendor/tap/tool"]
        )
        self.assertEqual(store.get(FactRef("demo", "casks")).value, ["firefox"])

    def test_absent_command_and_probe_failure_facts(self) -> None:
        self.module(facts={"packages": {"brew.formulae": {"command": str(self.brew)}}})
        self.state(fail="list")
        store = repository_facts(load_repository(self.root), self.registry)
        self.assertEqual(store.get(FactRef("demo", "packages")).state, FactState.ERROR)
        self.brew.unlink()
        store = repository_facts(load_repository(self.root), self.registry)
        self.assertEqual(
            store.get(FactRef("demo", "packages")).state, FactState.UNAVAILABLE
        )

    def staged(self) -> None:
        tool = str(self.bin / "installed-tool")
        self.module(
            facts={
                "tool": {"command": tool},
                "version": {"version": {"command": [tool, "--version"]}},
                "packages": {"brew.formulae": {"command": str(self.brew)}},
            },
            actions=[
                {
                    "brew": {"command": str(self.brew), "formulae": ["tool"]},
                    "refresh": ["tool", "version", "packages"],
                },
                {
                    "create": ["version-configured"],
                    "when": {"fact": {"name": "version", "matches": ">=2"}},
                },
                {
                    "create": ["command-configured"],
                    "when": {"fact": {"name": "tool", "equals": True}},
                },
                {
                    "create": ["packages-configured"],
                    "when": {"fact": {"name": "packages", "equals": ["tool"]}},
                },
            ],
        )

    def test_install_refresh_command_and_version_then_second_apply_noop(self) -> None:
        self.state(formula=[], cask=[], produce=True)
        self.staged()
        repository = load_repository(self.root)
        report = apply_repository(repository, self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        for path in ("version-configured", "command-configured", "packages-configured"):
            self.assertTrue((self.root / path).is_dir())
        second = apply_repository(repository, self.registry, jobs=2)
        self.assertTrue(second.succeeded, second.error)
        self.assertTrue(
            all(result.status is Status.SKIPPED for result in second.actions)
        )
        self.assertEqual(
            len([call for call in self.calls() if call["args"][0] == "install"]), 1
        )

    def test_failed_producer_blocks_configuration_and_refresh(self) -> None:
        self.state(formula=[], cask=[], fail="install")
        self.staged()
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertFalse(report.succeeded)
        self.assertEqual(report.actions[0].status, Status.FAILED)
        self.assertTrue(
            all(result.status is Status.BLOCKED for result in report.actions[1:])
        )
        observed = report.facts[FactRef("demo", "version")]
        assert observed is not None
        self.assertEqual(observed.state, FactState.UNAVAILABLE)

    def test_parallel_modules_serialize_brew_and_allow_unrelated_progress(self) -> None:
        self.state(formula=[], cask=[], gate=True)
        for name, package in (("a", "git"), ("b", "tmux")):
            self.module(
                name,
                actions=[{"brew": {"command": str(self.brew), "formulae": [package]}}],
            )
        script = """import sys, time
from pathlib import Path
root = Path(sys.argv[1])
deadline = time.monotonic() + 5
while not (root / 'started').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('brew did not start')
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
        self.assertEqual(
            [call["args"] for call in self.calls() if call["args"][0] == "install"],
            [["install", "--formula", "git"], ["install", "--formula", "tmux"]],
        )
        self.assertFalse((self.bin / "install.lock").exists())

    def test_module_dependency_can_use_packages_from_prior_module(self) -> None:
        self.state(formula=[], cask=[], dependencies=["tmux"])
        self.module(
            "a", actions=[{"brew": {"command": str(self.brew), "formulae": ["git"]}}]
        )
        self.module(
            "b",
            requires=["a"],
            actions=[{"brew": {"command": str(self.brew), "formulae": ["tmux"]}}],
        )
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(report.actions[1].status, Status.SKIPPED)
        self.assertEqual(
            len([call for call in self.calls() if call["args"][0] == "install"]), 1
        )

    def test_isolated_runtime_and_python39_grammar(self) -> None:
        self.module(
            actions=[{"brew": {"command": str(self.brew), "formulae": ["git"]}}]
        )
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
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for path in (ROOT / "plugins/homebrew").glob("*.py"):
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))
