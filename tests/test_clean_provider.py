from pathlib import Path
import tempfile
import unittest

from etchlib.core import core_registry
from etchlib.config import Module, Repository
from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.ownership.snapshot import validate_snapshot
from etchlib.ownership.claims import OwnershipError
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.filesystem.receipts import owned, receipt_path
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import PlanStatus


class CleanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.module = self.root / "module"
        self.module.mkdir()
        self.source = self.module / "config"
        self.source.write_text("hello")
        self.targets = self.root / "targets"
        self.targets.mkdir()
        self.context = Context(self.root, self.module, "demo", {})
        self.registry = core_registry()

    def plan(self, name, config):
        return plan_action(self.registry.action(name), config, self.context)

    def managed(self, name="config"):
        path = self.targets / name
        plan = self.plan("link", {str(path): "config"})
        self.registry.action("link").provider.apply(plan, self.context)
        return path

    def clean(self, config=None):
        return self.plan("clean", config if config is not None else [str(self.targets)])

    def apply(self, plan):
        return self.registry.action("clean").provider.apply(plan, self.context)

    def test_link_records_provenance_and_clean_removes_broken_link(self):
        path = self.managed()
        self.assertTrue(owned(self.root, path))
        self.source.unlink()
        plan = self.clean()
        self.assertTrue(path.is_symlink())
        self.assertEqual(plan.claims[0].path, path)
        self.assertTrue(self.apply(plan).changed)
        self.assertFalse(path.is_symlink())
        self.assertEqual(self.clean().status, PlanStatus.SKIP)
        self.assertFalse(self.apply(plan).changed)

    def test_valid_managed_link_requires_explicit_retirement(self):
        path = self.managed()
        self.assertEqual(self.clean().status, PlanStatus.SKIP)
        plan = self.clean({"paths": [str(self.targets)], "obsolete": [str(path)]})
        self.assertTrue(self.apply(plan).changed)
        self.assertTrue(self.source.exists())

    def test_unmanaged_broken_links_files_and_directories_are_preserved(self):
        link = self.targets / "unknown"
        link.symlink_to(self.root / "missing")
        (self.targets / "file").write_text("preserve")
        (self.targets / "directory").mkdir()
        self.assertEqual(self.clean().status, PlanStatus.SKIP)
        self.assertFalse(self.apply(self.clean()).changed)
        self.assertTrue(link.is_symlink())

    def test_matching_preexisting_link_is_not_adopted(self):
        path = self.targets / "preexisting"
        path.symlink_to(self.source)
        plan = self.plan("link", {str(path): "config"})
        self.registry.action("link").provider.apply(plan, self.context)
        self.assertFalse(owned(self.root, path))
        self.source.unlink()
        self.assertEqual(self.clean().status, PlanStatus.SKIP)

    def test_changed_link_is_no_longer_owned(self):
        path = self.managed()
        path.unlink()
        path.symlink_to(self.root / "different")
        self.assertFalse(owned(self.root, path))
        self.assertEqual(self.clean().status, PlanStatus.SKIP)

    def test_malformed_or_missing_receipt_preserves_link(self):
        path = self.managed()
        self.source.unlink()
        receipt = receipt_path(self.root, path)
        receipt.write_text("invalid")
        self.assertEqual(self.clean().status, PlanStatus.SKIP)
        receipt.unlink()
        self.assertEqual(self.clean().status, PlanStatus.SKIP)

    def test_reappeared_target_prevents_broken_link_removal(self):
        path = self.managed()
        self.source.unlink()
        plan = self.clean()
        self.source.write_text("restored")
        self.assertFalse(self.apply(plan).changed)
        self.assertTrue(path.is_symlink())

    def test_file_replacing_link_after_plan_is_preserved(self):
        path = self.managed()
        self.source.unlink()
        plan = self.clean()
        path.unlink()
        path.write_text("new user file")
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertEqual(path.read_text(), "new user file")

    def test_no_recursion_or_symlink_root_traversal(self):
        path = self.managed()
        self.source.unlink()
        self.assertEqual(self.plan("clean", [str(self.root)]).status, PlanStatus.SKIP)
        alias = self.root / "alias"
        alias.symlink_to(self.targets)
        with self.assertRaises(ProviderError):
            self.plan("clean", [str(alias)])
        self.assertTrue(path.is_symlink())

    def test_retirement_must_stay_inside_selected_directory(self):
        with self.assertRaises(ProviderError):
            self.clean({"paths": [str(self.targets)], "obsolete": [str(self.root / "outside")]})

    def test_no_receipt_directory_writes_during_planning(self):
        self.plan("link", {str(self.targets / "config"): "config"})
        self.clean()
        self.assertFalse((self.root / ".etch").exists())

    def test_retired_link_conflicts_with_active_link_owner(self):
        path = self.managed()
        actions = [{"link": {str(path): "config"}},
                   {"clean": {"paths": [str(self.targets)], "obsolete": [str(path)]}}]
        module = Module("demo", self.module, {"actions": actions})
        repo = Repository(self.root, (module,), {})
        selections = {"demo": Selection(Result(Outcome.TRUE), (Result(Outcome.TRUE), Result(Outcome.TRUE)))}
        with self.assertRaises(OwnershipError):
            validate_snapshot(repo, selections, self.registry)
        self.assertTrue(path.is_symlink())
