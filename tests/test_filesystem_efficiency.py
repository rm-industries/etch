"""Retained filesystem intent still checks current state before mutation."""

import sys
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.providers.filesystem.link import LinkProvider
from tests.planning_fixtures import PlanningFixture


class FilesystemEfficiencyTests(PlanningFixture):
    def test_link_is_inspected_once_after_unrelated_creation(self) -> None:
        self.module(actions=[{"create": ["unrelated"]}, {"link": {"linked": "source"}}])
        (self.root / "modules/demo/source").write_text("content")
        with patch.object(
            LinkProvider, "inspect", autospec=True, side_effect=LinkProvider.inspect
        ) as inspect:
            report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertTrue((self.root / "linked").is_symlink())
        self.assertEqual(inspect.call_count, 1)

    def test_conflict_created_after_inspection_is_preserved(self) -> None:
        command = [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; Path(sys.argv[1]).write_text('preserve')",
            str(self.root / "linked"),
        ]
        self.module(
            actions=[{"shell": {"command": command}}, {"link": {"linked": "source"}}]
        )
        (self.root / "modules/demo/source").write_text("content")
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertFalse(report.succeeded)
        self.assertEqual((self.root / "linked").read_text(), "preserve")

    def test_source_alias_is_reinspected_after_retargeting(self) -> None:
        self.module(
            actions=[
                {
                    "shell": {
                        "command": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; p=Path('alias'); p.unlink(); p.symlink_to('replacement')",
                        ]
                    }
                },
                {"link": {"linked": "alias"}},
            ]
        )
        root = self.root / "modules/demo"
        (root / "source").write_text("original")
        (root / "replacement").write_text("replacement")
        (root / "alias").symlink_to("source")
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual((self.root / "linked").resolve(), root / "replacement")
