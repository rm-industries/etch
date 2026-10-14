"""Explicit repository sources preserve module boundaries and link safety."""

import tempfile
import unittest
from pathlib import Path

from etchlib.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import PlanStatus


class RepoLinkTests(unittest.TestCase):
    def test_exposes_repo_file_idempotently_and_preserves_conflicts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="etch repo with spaces ") as temp:
            root = Path(temp).resolve()
            module = root / "modules/launcher"
            module.mkdir(parents=True)
            (root / "etch").write_text("launcher")
            (module / "etch").write_text("module asset")
            target = root / "home/.local/bin/etch"
            context = Context(root, module, "launcher", {})
            provider = core_registry().action("link")
            config = {
                str(target): {
                    "path": "etch",
                    "source_scope": "repo",
                    "create": True,
                    "relink": True,
                }
            }
            plan = plan_action(provider, config, context)
            self.assertIn(str(root / "etch"), plan.description)
            self.assertFalse(target.exists())
            self.assertTrue(provider.provider.apply(plan, context).changed)
            self.assertEqual(target.resolve(), root / "etch")
            self.assertEqual(
                plan_action(provider, config, context).status, PlanStatus.SKIP
            )
            self.assertFalse(provider.provider.apply(plan, context).changed)
            legacy = plan_action(provider, {str(root / "module-link"): "etch"}, context)
            self.assertEqual(legacy.payload[0].source, module / "etch")
            for directory in (False, True):
                target.unlink()
                target.mkdir() if directory else target.write_text("keep")
                with self.assertRaisesRegex(ValueError, "refusing to replace"):
                    plan_action(provider, config, context)
                self.assertTrue(
                    target.is_dir() if directory else target.read_text() == "keep"
                )
                target.rmdir() if directory else target.unlink()
                target.symlink_to(root / "etch")

    def test_rejects_scope_errors_and_escape_at_plan_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            outer = Path(temp).resolve()
            root = outer / "repo"
            module = root / "modules/example"
            module.mkdir(parents=True)
            (outer / "outside").write_text("outside")
            (root / "alias").symlink_to(outer / "outside")
            (root / "owned").write_text("owned")
            context = Context(root, module, "example", {})
            provider = core_registry().action("link")
            target = outer / "destination"
            for path, scope in (
                ("../outside", "repo"),
                (str(outer / "outside"), "repo"),
                ("alias", "repo"),
                ("owned", "unknown"),
                ("../../owned", "module"),
            ):
                with (
                    self.subTest(path=path, scope=scope),
                    self.assertRaises(ValueError),
                ):
                    plan_action(
                        provider,
                        {str(target): {"path": path, "source_scope": scope}},
                        context,
                    )
            plan = plan_action(
                provider,
                {str(target): {"path": "owned", "source_scope": "repo"}},
                context,
            )
            (root / "owned").unlink()
            (root / "owned").symlink_to(outer / "outside")
            with self.assertRaises(ValueError):
                provider.provider.apply(plan, context)
            self.assertFalse(target.exists())
