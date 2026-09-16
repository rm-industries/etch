"""Temporary consumer repositories for end-to-end planning checks."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import Any

from etchlib.cli import main
from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.planning.build import Report, plan_repository


class PlanningFixture(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.registry = core_registry()

    def write(self, relative: str, value: Any) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(repr(value), encoding="utf-8")

    def module(self, name: str = "demo", **options: Any) -> None:
        self.write(
            "modules/{}/module.conf".format(name),
            dict(schema_version=1, name=name, **options),
        )

    def plan(self) -> Report:
        return plan_repository(load_repository(self.root), self.registry)

    def cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(["plan", "--repo", str(self.root), *args])
        return status, out.getvalue(), err.getvalue()
