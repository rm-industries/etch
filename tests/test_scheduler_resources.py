import unittest
from typing import Any
from unittest.mock import patch

from etchlib.config import load_repository
from etchlib.execution.runner import apply_repository
from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactRef
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus
from etchlib.scheduling.resources import Resources, options, requirements
from tests.execution_fixtures import ExecutionFixture


class ResourceTests(unittest.TestCase):
    def test_invalid_configuration_and_reserved_capacities(self) -> None:
        cases: tuple[dict[str, Any], ...] = (
            {"jobs": True},
            {"jobs": 0},
            {"jobs": 65},
            {"other": 1},
            {"resources": []},
            {"resources": {"bad name": 1}},
            {"resources": {"x": False}},
            {"resources": {"x": 0}},
            {"resources": {"terminal": 2}},
            {"resources": {"sudo-interactive": 2}},
            {"resources": {"stdin-interactive": 2}},
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                options(value)

    def test_acquisition_is_atomic_and_release_restores_capacity(self) -> None:
        pool = Resources({"network": 2})
        pool.acquire(frozenset({"package-manager:example"}))
        with self.assertRaises(ValueError):
            pool.acquire(frozenset({"network", "package-manager:example"}))
        self.assertNotIn("network", pool.used)
        pool.acquire(frozenset({"network"}))
        self.assertTrue(pool.available(frozenset({"network"})))
        pool.release(frozenset({"package-manager:example"}))
        self.assertTrue(pool.available(frozenset({"package-manager:example"})))

    def test_privilege_and_stdin_share_one_terminal(self) -> None:
        privileged = requirements(Plan(PlanStatus.RUN, "sudo", elevated=True))
        interactive = requirements(
            Plan(PlanStatus.RUN, "stdin", resources=("stdin-interactive",))
        )
        pool = Resources({})
        pool.acquire(privileged)
        self.assertFalse(pool.available(interactive))
        pool.release(privileged)
        self.assertTrue(pool.available(interactive))

    def test_cli_jobs_override_configuration(self) -> None:
        self.assertEqual(options({"jobs": 4}, 1).jobs, 1)


class SchedulerValidationTests(ExecutionFixture):
    def test_invalid_resource_names_fail_before_any_apply(self) -> None:
        self.module(
            actions=[{"establish": {"name": "invalid", "resources": ["bad name"]}}]
        )
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertFalse(report.succeeded)
        self.assertEqual(self.action.applied, [])

    def test_unavailable_after_producer_failure_blocks_configuration(self) -> None:
        self.staged(fail=True)
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertFalse(report.succeeded)
        self.assertEqual(self.action.applied, ["install"])
        self.assertEqual(self.fact.calls, ["tool"])

    def test_worker_observations_are_detached_and_do_not_gather(self) -> None:
        self.fact.values["tool"] = ["original"]
        self.module(
            facts={"tool": {"state": "tool"}},
            actions=[{"establish": {"name": "consume", "facts": [["demo", "tool"]]}}],
        )
        original = self.action.apply

        def apply(plan: Plan, context: Context) -> ApplyResult:
            context.facts[FactRef("demo", "tool")].value.append("worker")
            return original(plan, context)

        with patch.object(self.action, "apply", side_effect=apply):
            report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.fact.calls, ["tool"])
        observed = report.facts[FactRef("demo", "tool")]
        assert observed is not None
        self.assertEqual(observed.value, ["original"])

    def test_false_resolution_unblocks_following_activated_action(self) -> None:
        self.fact.values["later"] = []
        self.module(
            facts={name: {"state": name} for name in ("tool", "flag", "later")},
            actions=[
                {
                    "establish": {
                        "name": "install",
                        "values": {"tool": "1", "flag": False, "later": ["yes"]},
                    },
                    "refresh": ["tool", "flag", "later"],
                },
                {
                    "establish": {"name": "configure"},
                    "when": {"fact": {"name": "tool", "matches": ">=1"}},
                },
                {
                    "establish": {"name": "skip"},
                    "when": {"fact": {"name": "flag", "equals": True}},
                },
                {
                    "establish": {"name": "last"},
                    "when": {"fact": {"name": "later", "equals": ["yes"]}},
                },
            ],
        )
        report = apply_repository(load_repository(self.root), self.registry, jobs=2)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual(self.action.applied, ["install", "configure", "last"])
