import unittest
from pathlib import Path

from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import gather_fact, plan_action
from etchlib.providers.observations import FactState
from etchlib.providers.plans import ApplyResult, PlanStatus
from etchlib.providers.registry import Origin, Registry
from tests.provider_fixtures import MemoryAction, MemoryFact


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.context = Context(
            Path("/consumer"), Path("/consumer/modules/example"), "example", {}
        )
        self.registry = Registry()

    def test_core_and_external_actions_share_contract(self):
        for origin in [
            Origin("Etch core", "0.1.0", True),
            Origin("etch-example", "1.2.0"),
        ]:
            with self.subTest(origin=origin):
                registry = Registry()
                provider = MemoryAction()
                registry.register(origin, [provider])
                entry = registry.action("memory")
                plan = plan_action(entry, {"value": "desired"}, self.context)
                self.assertEqual(provider.calls, ["validate", "inspect", "plan"])
                self.assertIsNone(provider.value)  # Planning never applies.
                self.assertEqual(plan.status, PlanStatus.CHANGE)
                self.assertEqual(plan.requires, ("base",))
                self.assertEqual(plan.refresh[0].module, "example")
                self.assertEqual(plan.resources, ("application:memory",))
                self.assertEqual(
                    plan.claims[0].path, self.context.module_root / "config"
                )
                # Explicit fixture application tests the protocol, not an engine bypass.
                result = entry.provider.apply(plan, self.context)
                self.assertIsInstance(result, ApplyResult)
                self.assertTrue(result.changed)
                self.assertEqual(
                    plan_action(entry, {"value": "desired"}, self.context).status,
                    PlanStatus.SKIP,
                )

    def test_validation_failure_prevents_inspection(self):
        action = MemoryAction()
        self.registry.register(Origin("example", "1"), [action])
        with self.assertRaisesRegex(
            ProviderError, "validate failed: value is required"
        ):
            plan_action(self.registry.action("memory"), {}, self.context)
        self.assertEqual(action.calls, ["validate"])

    def test_invalid_result_types(self):
        for method, value in [("validate", False), ("inspect", {}), ("plan", {})]:
            action = MemoryAction()
            setattr(action, method, lambda *args, value=value: value)
            registry = Registry()
            registry.register(Origin("example", "1"), [action])
            with (
                self.subTest(method=method),
                self.assertRaisesRegex(ProviderError, method),
            ):
                plan_action(registry.action("memory"), {"value": 1}, self.context)
            self.assertIsNone(action.value)

    def test_fact_contract_and_wrong_kind(self):
        self.registry.register(Origin("example", "1"), facts=[MemoryFact()])
        entry = self.registry.fact("memory_value")
        self.assertEqual(
            gather_fact(entry, {"value": 42}, self.context).state, FactState.VALUE
        )
        self.assertEqual(gather_fact(entry, {"value": 42}, self.context).value, 42)
        with self.assertRaisesRegex(ProviderError, "expected action"):
            plan_action(entry, {}, self.context)
        entry.provider.gather = lambda *args: 42
        with self.assertRaisesRegex(ProviderError, "must return FactResult"):
            gather_fact(entry, {}, self.context)
