import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from etchlib.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import ApplyResult, ClaimKind, Plan, PlanStatus


class FilesystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.module = self.root / "module"
        (self.module / "files").mkdir(parents=True)
        (self.module / "files/config").write_text("hello")
        self.context = Context(self.root, self.module, "demo", {})
        self.registry = core_registry()

    def plan(self, name: str, config: Any) -> Plan:
        return plan_action(self.registry.action(name), config, self.context)

    def apply(self, name: str, plan: Plan) -> ApplyResult:
        result = self.registry.action(name).provider.apply(plan, self.context)
        assert isinstance(result, ApplyResult)
        return result

    def test_create_plans_without_mutation_and_is_idempotent(self) -> None:
        target = self.root / "nested/dir"
        plan = self.plan("create", [str(target)])
        self.assertFalse(target.exists())
        self.assertEqual(plan.claims[0].kind, ClaimKind.SHARED_DIRECTORY)
        self.assertTrue(self.apply("create", plan).changed)
        self.assertEqual(self.plan("create", [str(target)]).status, PlanStatus.SKIP)
        self.assertFalse(self.apply("create", plan).changed)

    def test_create_rejects_regular_file_and_broken_link(self) -> None:
        file = self.root / "file"
        file.write_text("preserve")
        broken = self.root / "broken"
        broken.symlink_to(self.root / "missing")
        for path in (file, broken):
            with self.assertRaises(ProviderError):
                self.plan("create", [str(path)])

    def test_link_plans_without_mutation_and_is_idempotent(self) -> None:
        target = self.root / "config"
        config = {str(target): "files/config"}
        plan = self.plan("link", config)
        self.assertFalse(target.exists())
        self.assertTrue(self.apply("link", plan).changed)
        self.assertEqual(target.resolve(), self.module / "files/config")
        self.assertEqual(self.plan("link", config).status, PlanStatus.SKIP)
        self.assertFalse(self.apply("link", plan).changed)

    def test_parent_creation_is_explicit(self) -> None:
        target = self.root / "nested/config"
        with self.assertRaisesRegex(ProviderError, "enable create"):
            self.plan("link", {str(target): "files/config"})
        plan = self.plan(
            "link", {str(target): {"path": "files/config", "create": True}}
        )
        self.assertFalse(target.parent.exists())
        self.assertTrue(self.apply("link", plan).changed)

    def test_wrong_and_broken_links_require_relink(self) -> None:
        for source in [self.root / "missing", self.module / "files"]:
            target = self.root / "config"
            target.symlink_to(source)
            with self.assertRaisesRegex(ProviderError, "enable relink"):
                self.plan("link", {str(target): "files/config"})
            plan = self.plan(
                "link", {str(target): {"path": "files/config", "relink": True}}
            )
            self.assertTrue(self.apply("link", plan).changed)
            self.assertEqual(target.read_text(), "hello")
            target.unlink()

    def test_relink_never_replaces_regular_files(self) -> None:
        target = self.root / "config"
        target.write_text("preserve")
        with self.assertRaises(ProviderError):
            self.plan("link", {str(target): {"path": "files/config", "relink": True}})
        self.assertEqual(target.read_text(), "preserve")

    def test_module_relocation(self) -> None:
        moved = self.root / "moved"
        shutil.move(str(self.module), str(moved))
        self.context = Context(self.root, moved, "demo", {})
        plan = self.plan("link", {str(self.root / "config"): "files/config"})
        self.apply("link", plan)
        self.assertEqual((self.root / "config").resolve(), moved / "files/config")

    def test_apply_preflights_all_destinations_before_mutating(self) -> None:
        first, second = self.root / "one", self.root / "two"
        plan = self.plan(
            "link", {str(first): "files/config", str(second): "files/config"}
        )
        second.write_text("appeared since planning")
        with self.assertRaises(ValueError):
            self.apply("link", plan)
        self.assertFalse(first.exists())
        self.assertEqual(second.read_text(), "appeared since planning")

    def test_defaults_can_be_overridden_per_link(self) -> None:
        self.context = Context(
            self.root, self.module, "demo", {}, {"link": {"create": True}}
        )
        self.assertEqual(
            self.plan("link", {"nested/config": "files/config"}).status,
            PlanStatus.CHANGE,
        )
        with self.assertRaises(ProviderError):
            self.plan(
                "link", {"nested/config": {"path": "files/config", "create": False}}
            )

    def test_invalid_options_missing_sources_and_escapes(self) -> None:
        for config in [
            {"out": {"path": "files/config", "create": "yes"}},
            {"out": {"path": "files/config", "force": True}},
            {"out": "files/missing"},
            {"out": "../outside"},
        ]:
            with self.subTest(config=config), self.assertRaises(ProviderError):
                self.plan("link", config)

    def test_nested_destinations_are_rejected_within_one_action(self) -> None:
        with self.assertRaises(ProviderError):
            self.plan("link", {"out": "files/config", "out/child": "files/config"})
