import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

from etchlib.providers.observations import FactRef, FactResult, FactState, Inspection
from etchlib.providers.plans import PathClaim, Plan, PlanStatus


class RecordTests(unittest.TestCase):
    def test_plan_requires_typed_metadata(self) -> None:
        invalid_options: list[dict[str, Any]] = [
            {"resources": ["network"]},
            {"refresh": ("version",)},
            {"elevated": "yes"},
            {"claims": ("/tmp/config",)},
            {"requires": ("",)},
        ]
        for options in invalid_options:
            with self.subTest(options=options), self.assertRaises(ValueError):
                Plan(PlanStatus.RUN, "Run something", **options)
        with self.assertRaises(ValueError):
            Plan("run", "Run something")  # type: ignore[arg-type]  # Test runtime validation.

    def test_records_have_frozen_fields(self) -> None:
        plan = Plan(PlanStatus.RUN, "Install software", network=True, opaque=True)
        with self.assertRaises(FrozenInstanceError):
            plan.network = False  # type: ignore[misc]  # Verify runtime immutability.

    def test_claims_require_absolute_paths(self) -> None:
        with self.assertRaises(ValueError):
            PathClaim(Path("relative"))

    def test_fact_states_and_scoping(self) -> None:
        self.assertNotEqual(FactRef("one", "version"), FactRef("two", "version"))
        self.assertIsNone(FactResult(FactState.VALUE, None).value)
        self.assertEqual(FactResult(FactState.STALE, "old").value, "old")
        for state in [FactState.UNAVAILABLE, FactState.ERROR]:
            with self.assertRaises(ValueError):
                FactResult(state)
            result = FactResult(state, reason="command not found")
            self.assertEqual(result.state, state)
        with self.assertRaises(ValueError):
            Inspection("unknown")  # type: ignore[arg-type]  # Test runtime validation.
