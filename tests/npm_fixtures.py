"""Load the independent npm bundle against a disposable native CLI."""

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from etchlib.core import core_registry
from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import Plan
from tests.planning_fixtures import PlanningFixture

ROOT = Path(__file__).resolve().parents[1]


class NpmFixture(PlanningFixture):
    def setUp(self) -> None:
        super().setUp()
        self.bin = self.root / "fake bin"
        self.bin.mkdir()
        (self.bin / "global/lib").mkdir(parents=True)
        self.npm = self.bin / "npm"
        python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
        self.npm.write_text(
            "#!" + python + "\n" + (ROOT / "tests/fixtures/npm_cli.py").read_text()
        )
        self.npm.chmod(0o755)
        self.state()
        self.module()
        self.context = Context(self.root, self.root / "modules/demo", "demo", {})
        shutil.copytree(
            ROOT / "plugins/npm",
            self.root / "vendor/npm",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.write("defaults.conf", {"schema_version": 1, "plugins": ["vendor/npm"]})
        self.registry = load_plugins(
            self.root, ["vendor/npm"], core_registry()
        ).registry
        self.entry = self.registry.action("npm")

    def state(self, **values: Any) -> None:
        (self.bin / "state.json").write_text(json.dumps(values))

    def current(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads((self.bin / "state.json").read_text())
        return value

    def calls(self) -> list[list[str]]:
        path = self.bin / "calls.jsonl"
        return (
            [json.loads(line)["args"] for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def installs(self) -> list[list[str]]:
        return [
            [spec[:-2] for spec in args[args.index("--") + 1 :]]
            for args in self.calls()
            if args[0] == "install"
        ]

    def npm_plan(self, **values: Any) -> Plan:
        return plan_action(
            self.entry, {"command": str(self.npm), **values}, self.context
        )
