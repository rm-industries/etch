"""Real source-plugin loading with a temporary fake Homebrew executable."""

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


class BrewFixture(PlanningFixture):
    def setUp(self) -> None:
        super().setUp()
        self.bin = self.root / "fake bin"
        self.bin.mkdir()
        self.brew = self.bin / "fake brew"
        python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
        self.brew.write_text(
            "#!" + python + "\n" + (ROOT / "tests/fixtures/brew_cli.py").read_text()
        )
        self.brew.chmod(0o755)
        self.state(formula=[], cask=[])
        self.module()
        self.context = Context(self.root, self.root / "modules/demo", "demo", {})
        shutil.copytree(
            ROOT / "plugins/homebrew",
            self.root / "vendor/etch-homebrew",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.write(
            "defaults.conf", {"schema_version": 1, "plugins": ["vendor/etch-homebrew"]}
        )
        self.registry = load_plugins(
            self.root, ["vendor/etch-homebrew"], core_registry()
        ).registry
        self.entry = self.registry.action("brew")

    def state(self, **values: Any) -> None:
        (self.bin / "state.json").write_text(json.dumps(values))

    def current(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads((self.bin / "state.json").read_text())
        return value

    def calls(self) -> list[dict[str, Any]]:
        path = self.bin / "calls.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def brew_plan(self, **options: Any) -> Plan:
        return plan_action(
            self.entry, dict(command=str(self.brew), **options), self.context
        )
