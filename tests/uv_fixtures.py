"""Load the independent uv bundle against a disposable native CLI."""

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


class UvFixture(PlanningFixture):
    def setUp(self) -> None:
        super().setUp()
        self.bin = self.root / "fake bin"
        self.bin.mkdir()
        self.command = self.bin / "uv"
        python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
        self.command.write_text(
            "#!" + python + "\n" + (ROOT / "tests/fixtures/uv_cli.py").read_text()
        )
        self.command.chmod(0o755)
        self.state()
        self.module()
        self.context = Context(self.root, self.root / "modules/demo", "demo", {})
        shutil.copytree(
            ROOT / "plugins/uv",
            self.root / "vendor/uv",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.write("defaults.conf", {"schema_version": 1, "plugins": ["vendor/uv"]})
        self.registry = load_plugins(self.root, ["vendor/uv"], core_registry()).registry
        self.entry = self.registry.action("uv")

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
            args[args.index("--") + 1 :]
            for args in self.calls()
            if args[:2] == ["tool", "install"]
        ]

    def uv_plan(self, **values: Any) -> Plan:
        return plan_action(
            self.entry, {"command": str(self.command), **values}, self.context
        )
