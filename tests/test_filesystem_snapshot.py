import tempfile
import unittest
from pathlib import Path

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.config import Module, Repository
from etchlib.core import core_registry
from etchlib.ownership.claims import OwnershipError
from etchlib.ownership.snapshot import validate_snapshot


class FilesystemSnapshotTests(unittest.TestCase):
    def test_core_providers_defaults_and_conflicting_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "source").write_text("hello")
            module = Module(
                "demo", root, {"actions": [{"link": {"nested/config": "source"}}]}
            )
            repo = Repository(root, (module,), {"defaults": {"link": {"create": True}}})
            selections = {
                "demo": Selection(Result(Outcome.TRUE), (Result(Outcome.TRUE),))
            }
            snapshot = validate_snapshot(repo, selections, core_registry())
            self.assertEqual(len(snapshot.plans), 1)
            self.assertFalse((root / "nested").exists())
            module.config["actions"].append({"link": {"nested/config": "source"}})
            selections["demo"] = Selection(
                Result(Outcome.TRUE), (Result(Outcome.TRUE), Result(Outcome.TRUE))
            )
            with self.assertRaises(OwnershipError):
                validate_snapshot(repo, selections, core_registry())
            self.assertFalse((root / "nested").exists())
