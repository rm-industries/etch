"""Native filesystem contract, also exercised on Unix without optional tools."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from etchlib.config import ConfigError, Module, destination
from etchlib.core import core_registry
from etchlib.ownership.claims import OwnershipError, validate_claims
from etchlib.providers.contracts import Context
from etchlib.providers.filesystem.state import kind
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import PlanStatus


class WindowsFilesystemTests(unittest.TestCase):
    def test_create_link_clean_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="etch filesystem ") as temp:
            root = Path(temp).resolve()
            module = root / "module"
            module.mkdir()
            source = module / "settings"
            source.write_text("keep", encoding="utf-8")
            folder = module / "folder"
            folder.mkdir()
            registry = core_registry()
            context = Context(root, module, "demo", {})
            create = registry.action("create")
            plan = plan_action(create, ["targets/nested"], context)
            self.assertFalse((root / "targets").exists())
            self.assertTrue(create.provider.apply(plan, context).changed)
            self.assertEqual(
                plan_action(create, ["targets/nested"], context).status, PlanStatus.SKIP
            )
            link = registry.action("link")
            config = {
                str(root / "targets" / "settings"): "settings",
                str(root / "targets" / "folder"): "folder",
            }
            plan = plan_action(link, config, context)
            self.assertTrue(link.provider.apply(plan, context).changed)
            self.assertEqual((root / "targets/folder").resolve(), folder)
            self.assertEqual(plan_action(link, config, context).status, PlanStatus.SKIP)
            with self.assertRaises(OwnershipError):
                validate_claims({"one": plan, "two": plan})
            other = module / "other"
            other.mkdir()
            relink = {str(root / "targets/folder"): {"path": "other", "relink": True}}
            self.assertTrue(
                link.provider.apply(plan_action(link, relink, context), context).changed
            )
            self.assertEqual((root / "targets/folder").resolve(), other)
            clean = registry.action("clean")
            source.unlink()
            plan = plan_action(clean, ["targets"], context)
            self.assertTrue(clean.provider.apply(plan, context).changed)
            self.assertTrue((root / "targets/folder").is_symlink())
            self.assertEqual(
                plan_action(clean, ["targets"], context).status, PlanStatus.SKIP
            )

    def test_privilege_failure_preserves_previous_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "source"
            source.touch()
            old = root / "old"
            old.touch()
            target = root / "target"
            target.symlink_to(old)
            context = Context(root, root, "demo", {})
            link = core_registry().action("link")
            plan = plan_action(
                link, {str(target): {"path": "source", "relink": True}}, context
            )
            error = OSError("privilege missing")
            error.__dict__["winerror"] = 1314
            with patch.object(Path, "symlink_to", side_effect=error):
                with self.assertRaisesRegex(ValueError, "Developer Mode"):
                    link.provider.apply(plan, context)
            self.assertEqual(target.resolve(), old)

    @unittest.skipUnless(os.name == "nt", "Windows path rules")
    def test_windows_paths_and_case_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self.assertEqual(destination(r"nested\file", root), root / "nested/file")
            self.assertEqual(destination("nested/file", root), root / "nested/file")
            for value in (r"C:relative", r"\rooted"):
                with self.assertRaises(ConfigError):
                    destination(value, root)
                with self.assertRaises(ConfigError):
                    Module("demo", root, {}).asset(value)
            context = Context(root, root, "demo", {})
            source = root / "source"
            source.touch()
            link = core_registry().action("link")
            first = plan_action(link, {str(root / "Config"): "source"}, context)
            second = plan_action(link, {str(root / "config"): "source"}, context)
            with self.assertRaises(OwnershipError):
                validate_claims({"first": first, "second": second})

    def test_junctions_are_not_classified_as_directories(self) -> None:
        info = SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0xA0000003)
        with patch.object(Path, "lstat", return_value=info):
            self.assertEqual(kind(Path("junction")), "reparse point")

    def test_failed_publication_preserves_previous_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "source").touch()
            (root / "old").touch()
            target = root / "target"
            target.symlink_to(root / "old")
            context = Context(root, root, "demo", {})
            link = core_registry().action("link")
            plan = plan_action(
                link, {str(target): {"path": "source", "relink": True}}, context
            )
            with patch(
                "etchlib.providers.filesystem.link.os.replace",
                side_effect=PermissionError("locked"),
            ):
                with self.assertRaises(PermissionError):
                    link.provider.apply(plan, context)
            self.assertEqual(target.resolve(), root / "old")
