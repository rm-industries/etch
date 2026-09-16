from unittest.mock import patch

from etchlib.execution.results import Status
from tests.execution_fixtures import ExecutionFixture


class ExecutionValidationTests(ExecutionFixture):
    def activated(self, config: dict[str, object]) -> None:
        self.module(
            facts={"tool": {"state": "tool"}},
            actions=[
                {
                    "establish": {
                        "name": "install",
                        "values": {"tool": "1"},
                        "claim": "owned",
                    },
                    "refresh": ["tool"],
                },
                {
                    "establish": dict(name="configure", **config),
                    "when": {"fact": {"name": "tool", "matches": ">=1"}},
                },
            ],
        )

    def test_newly_activated_work_gets_all_validations(self) -> None:
        cases: list[tuple[dict[str, object], str]] = [
            ({"invalid": True}, "bad activated configuration"),
            ({"claim": "owned"}, "conflict"),
            ({"requires": ["missing"]}, "missing, unselected or inactive"),
            ({"requires": ["demo"]}, "cycle"),
            ({"sudo": True}, "--allow-sudo"),
            ({"refreshes": [["demo", "missing"]]}, "undeclared fact"),
        ]
        for config, message in cases:
            with self.subTest(config=config):
                self.fact.values.clear()
                self.action.applied.clear()
                self.activated(config)
                report = self.apply_repo()
                self.assertFalse(report.succeeded)
                self.assertIn(message, report.error or "")
                self.assertEqual(self.action.applied, ["install"])
                self.assertEqual(report.actions[1].status, Status.BLOCKED)

    def test_invalid_activated_filesystem_source_is_rejected(self) -> None:
        self.module(
            facts={"tool": {"state": "tool"}},
            actions=[
                {
                    "establish": {"name": "install", "values": {"tool": "1"}},
                    "refresh": ["tool"],
                },
                {
                    "link": {str(self.root / "target"): "missing"},
                    "when": {"fact": {"name": "tool", "matches": ">=1"}},
                },
            ],
        )
        report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertIn("link source does not exist", report.error or "")
        self.assertFalse((self.root / "target").exists())

    def test_undeclared_refresh_fails_before_any_change_even_in_false_branch(
        self,
    ) -> None:
        self.module(
            actions=[
                {"establish": {"name": "first"}},
                {
                    "establish": {"name": "hidden"},
                    "when": {"os": "never"},
                    "refresh": ["unknown"],
                },
            ]
        )
        report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertEqual(self.action.applied, [])
        self.assertIn("undeclared refresh", report.error or "")

    def test_initial_conflict_prevents_all_mutations(self) -> None:
        self.module(
            actions=[
                {"establish": {"name": name, "claim": "owned"}} for name in ("a", "b")
            ]
        )
        report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertEqual(self.action.applied, [])

    def test_late_condition_cannot_insert_work_before_completed_actions(self) -> None:
        self.fact.values["tool"] = "0"
        self.module(
            facts={"tool": {"state": "tool"}},
            actions=[
                {
                    "establish": {"name": "early"},
                    "when": {"fact": {"name": "tool", "matches": ">=1"}},
                },
                {
                    "establish": {"name": "install", "values": {"tool": "1"}},
                    "refresh": ["tool"],
                },
            ],
        )
        report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertIn("already completed", report.error or "")
        self.assertEqual(self.action.applied, ["install"])

    def test_new_dependencies_reorder_pending_work(self) -> None:
        self.module("other", actions=[{"establish": {"name": "dependency"}}])
        self.activated({"requires": ["other"]})
        report = self.apply_repo()
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install", "dependency", "configure"])

    def test_initial_privilege_requests_are_rejected_before_any_action(self) -> None:
        self.module(
            actions=[
                {"establish": {"name": "first"}},
                {"establish": {"name": "sudo", "sudo": True}},
            ]
        )
        report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertEqual(self.action.applied, [])
        self.assertTrue(self.apply_repo(allow_sudo=True).succeeded)

    def test_bad_apply_result_is_failure_and_does_not_refresh(self) -> None:
        self.staged()
        with patch.object(self.action, "apply", return_value=None):
            report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertIn("apply must return ApplyResult", report.error or "")
        self.assertEqual(self.fact.calls, ["tool"])

    def test_interruption_preserves_failure_and_blocked_results(self) -> None:
        self.staged()
        with patch.object(self.action, "apply", side_effect=KeyboardInterrupt):
            report = self.apply_repo()
        self.assertFalse(report.succeeded)
        self.assertEqual(
            [result.status for result in report.actions],
            [Status.FAILED, Status.BLOCKED],
        )
        self.assertIn("partially changed", report.error or "")
