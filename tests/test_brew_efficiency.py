"""Stable package intent avoids repeated inventory reads between actions."""

from etchlib.config import load_repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from tests.brew_fixtures import BrewFixture


class BrewEfficiencyTests(BrewFixture):
    def test_unrelated_execution_does_not_reinspect_package_intent(self) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                self.state(formula=[], cask=[])
                (self.bin / "calls.jsonl").unlink(missing_ok=True)
                self.module(
                    actions=[
                        {"create": ["unrelated-{}".format(jobs)]},
                        {"brew": {"command": str(self.brew), "formulae": ["git"]}},
                        {"brew": {"command": str(self.brew), "formulae": ["tmux"]}},
                    ]
                )
                report = apply_repository(
                    load_repository(self.root), self.registry, jobs=jobs
                )
                self.assertTrue(report.succeeded, report.error)
                self.assertEqual(
                    len([c for c in self.calls() if c["args"][0] == "list"]), 6
                )
                self.assertEqual(self.current()["formula"], ["git", "tmux"])

    def test_overlapping_request_is_reconciled_at_execution(self) -> None:
        self.state(formula=[], cask=[], dependencies=["tmux"])
        self.module(
            actions=[
                {"brew": {"command": str(self.brew), "formulae": ["git"]}},
                {"brew": {"command": str(self.brew), "formulae": ["tmux"]}},
            ]
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(
            [r.status for r in report.actions], [Status.CHANGED, Status.UNCHANGED]
        )
        self.assertEqual(len([c for c in self.calls() if c["args"][0] == "install"]), 1)
