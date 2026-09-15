import tempfile
import unittest
from pathlib import Path

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.config import Module, Repository
from etchlib.graph.model import GraphError, NodeId
from etchlib.ownership.claims import OwnershipError
from etchlib.ownership.snapshot import validate_snapshot
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import PathClaim, Plan, PlanStatus
from etchlib.providers.registry import Origin, Registry


class ClaimProvider:
    name = "claim"

    def __init__(self):
        self.validations = 0
        self.applied = False

    def validate(self, config, context):
        self.validations += 1
        if not isinstance(config, dict) or "path" not in config:
            raise ValueError("path required")

    def inspect(self, config, context):
        return Inspection(InspectionState.CHANGE)

    def plan(self, config, observation, context):
        return Plan(
            PlanStatus.CHANGE,
            "test claim",
            claims=(PathClaim(Path(config["path"])),),
            elevated=config.get("elevated", False),
        )

    def apply(self, plan, context):
        self.applied = True
        raise AssertionError("validation must never apply")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.provider = ClaimProvider()
        self.registry = Registry()
        self.registry.register(Origin("test", "1"), actions=[self.provider])

    def snapshot(self, actions, outcomes):
        module = Module("demo", self.root, {"actions": actions})
        repository = Repository(self.root, (module,), {})
        selections = {
            "demo": Selection(Result(Outcome.TRUE), tuple(Result(o) for o in outcomes))
        }
        return repository, selections

    def test_refresh_activation_rechecks_claims_and_never_applies(self):
        actions = [{"claim": {"path": str(self.root / "file")}}] * 2
        repo, selections = self.snapshot(actions, [Outcome.TRUE, Outcome.DEFERRED])
        validate_snapshot(repo, selections, self.registry)
        self.assertEqual(self.provider.validations, 1)
        selections["demo"] = Selection(
            Result(Outcome.TRUE), (Result(Outcome.TRUE), Result(Outcome.TRUE))
        )
        with self.assertRaises(OwnershipError):
            validate_snapshot(repo, selections, self.registry)
        self.assertEqual(self.provider.validations, 3)
        self.assertFalse(self.provider.applied)

    def test_mutually_exclusive_branches_do_not_conflict(self):
        actions = [{"claim": {"path": str(self.root / "file")}}] * 2
        for outcomes in [[Outcome.TRUE, Outcome.FALSE], [Outcome.FALSE, Outcome.TRUE]]:
            repo, selections = self.snapshot(actions, outcomes)
            result = validate_snapshot(repo, selections, self.registry)
            self.assertEqual(len(result.claims), 1)

    def test_newly_active_provider_and_schema_are_revalidated(self):
        for action in [{"missing": {}}, {"claim": {}}]:
            repo, selections = self.snapshot([action], [Outcome.DEFERRED])
            validate_snapshot(repo, selections, self.registry)
            selections["demo"] = Selection(
                Result(Outcome.TRUE), (Result(Outcome.TRUE),)
            )
            with self.assertRaises(ProviderError):
                validate_snapshot(repo, selections, self.registry)
        self.assertFalse(self.provider.applied)

    def test_newly_active_dependency_is_revalidated(self):
        repo, selections = self.snapshot(
            [{"claim": {"path": str(self.root / "file")}, "requires": ["missing"]}],
            [Outcome.DEFERRED],
        )
        validate_snapshot(repo, selections, self.registry)
        selections["demo"] = Selection(Result(Outcome.TRUE), (Result(Outcome.TRUE),))
        with self.assertRaises(GraphError):
            validate_snapshot(repo, selections, self.registry)
        self.assertFalse(self.provider.applied)

    def test_privilege_requires_specific_action_authorization(self):
        repo, selections = self.snapshot(
            [{"claim": {"path": str(self.root / "file"), "elevated": True}}],
            [Outcome.TRUE],
        )
        with self.assertRaisesRegex(OwnershipError, "not been authorized"):
            validate_snapshot(repo, selections, self.registry)
        result = validate_snapshot(
            repo,
            selections,
            self.registry,
            elevated_actions=[NodeId("demo", "action", 0)],
        )
        self.assertEqual(len(result.plans), 1)
        self.assertFalse(self.provider.applied)
