"""Load the optional Codex bundle against a disposable native CLI double."""

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


class CodexFixture(PlanningFixture):
    def setUp(self) -> None:
        super().setUp()
        self.bin = self.root / "fake bin"
        self.bin.mkdir()
        self.code = self.bin / "codex"
        self.code.write_text(
            "#!"
            + str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
            + "\n"
            + (ROOT / "tests/fixtures/codex_cli.py").read_text()
        )
        self.code.chmod(0o755)
        self.state()
        self.module()
        self.context = Context(self.root, self.root / "modules/demo", "demo", {})
        shutil.copytree(
            ROOT / "plugins/codex",
            self.root / "vendor/codex",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.loaded = load_plugins(self.root, ["vendor/codex"], core_registry())
        self.registry = self.loaded.registry
        self.entry = self.registry.action("codex")

    def state(self, **values: Any) -> None:
        (self.bin / "state.json").write_text(json.dumps(values))

    def current(self) -> dict[str, Any]:
        values: dict[str, Any] = json.loads((self.bin / "state.json").read_text())
        return values

    def calls(self) -> list[list[str]]:
        path = self.bin / "calls.jsonl"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def codex_plan(self, **values: Any) -> Plan:
        return plan_action(
            self.entry, {"command": str(self.code), **values}, self.context
        )
