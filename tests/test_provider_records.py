from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest

from etchlib.providers.observations import FactRef, FactResult, FactState, Inspection
from etchlib.providers.plans import PathClaim, Plan, PlanStatus


class RecordTests(unittest.TestCase):
    def test_plan_requires_typed_metadata(self):
        for options in [{"resources": ["network"]}, {"refresh": ("version",)},
                        {"elevated": "yes"}, {"claims": ("/tmp/config",)},
                        {"requires": ("",)}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                Plan(PlanStatus.RUN, "Run something", **options)
        with self.assertRaises(ValueError):
            Plan("run", "Run something")

    def test_records_have_frozen_fields(self):
        plan = Plan(PlanStatus.RUN, "Install software", network=True, opaque=True)
        with self.assertRaises(FrozenInstanceError):
            plan.network = False

    def test_claims_require_absolute_paths(self):
        with self.assertRaises(ValueError):
            PathClaim(Path("relative"))

    def test_fact_states_and_scoping(self):
        self.assertNotEqual(FactRef("one", "version"), FactRef("two", "version"))
        self.assertIsNone(FactResult(FactState.VALUE, None).value)
        self.assertEqual(FactResult(FactState.STALE, "old").value, "old")
        for state in [FactState.UNAVAILABLE, FactState.ERROR]:
            with self.assertRaises(ValueError):
                FactResult(state)
            result = FactResult(state, reason="command not found")
            self.assertEqual(result.state, state)
        with self.assertRaises(ValueError):
            Inspection("unknown")
