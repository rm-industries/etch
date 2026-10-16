"""Ownership history retires removed declarations without consumer cleanup lists."""

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.config import load_repository
from etchlib.core import core_registry
from etchlib.execution.housekeeping import finish
from etchlib.execution.results import ExecutionReport
from etchlib.execution.runner import apply_repository
from etchlib.planning.build import plan_repository
from etchlib.planning.render import render_plan
from etchlib.providers.filesystem.receipts import receipt_path
from tests.planning_fixtures import PlanningFixture


class HousekeepingTests(PlanningFixture):
    def setup_link(self) -> None:
        self.module("demo", actions=[{"link": {"old": "source"}}])
        (self.root / "modules/demo/source").write_text("keep")
        self.registry = core_registry()
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.old = self.root / "old"
        self.receipt = receipt_path(self.root, self.old)

    def test_removed_declaration_is_previewed_and_retired_for_serial_and_parallel(
        self,
    ) -> None:
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                self.setup_link()
                self.module("demo", actions=[{"link": {"new": "source"}}])
                repository = load_repository(self.root)
                plan = plan_repository(repository, self.registry)
                self.assertIn("Retire link", render_plan(repository, plan))
                self.assertTrue(self.old.is_symlink())
                self.assertTrue(self.receipt.exists())
                applied = apply_repository(repository, self.registry, jobs=jobs)
                self.assertTrue(applied.succeeded, applied.error)
                self.assertFalse(self.old.is_symlink())
                self.assertFalse(self.receipt.exists())
                self.assertTrue((self.root / "new").is_symlink())
                self.assertNotIn(
                    "Retire link",
                    render_plan(repository, plan_repository(repository, self.registry)),
                )
                (self.root / "new").unlink()

    def test_removed_last_module_is_retired(self) -> None:
        self.setup_link()
        shutil.rmtree(self.root / "modules/demo")
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertFalse(self.old.is_symlink())
        self.assertFalse(self.receipt.exists())

    def test_partial_selection_and_false_conditions_preserve_links(self) -> None:
        self.setup_link()
        self.module("other", actions=[])
        self.module("demo", when={"os": "nonexistent"}, actions=[])
        for selected in (["other"], ["demo"]):
            report = apply_repository(
                load_repository(self.root, selected=selected), self.registry
            )
            self.assertTrue(report.succeeded, report.error)
            self.assertTrue(self.old.is_symlink())
            self.assertTrue(self.receipt.exists())

    def test_changed_file_is_preserved_but_stale_receipt_is_removed(self) -> None:
        self.setup_link()
        self.old.unlink()
        self.old.write_text("mine")
        self.module("demo", actions=[])
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertEqual(self.old.read_text(), "mine")
        self.assertFalse(self.receipt.exists())

    def test_failed_apply_does_not_retire_links(self) -> None:
        self.setup_link()
        self.module("demo", actions=[{"link": {"other": "missing"}}])
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertFalse(report.succeeded)
        self.assertTrue(self.old.is_symlink())
        self.assertTrue(self.receipt.exists())

    def test_live_declaration_in_another_module_protects_destination(self) -> None:
        self.setup_link()
        self.module("demo", actions=[])
        self.module(
            "other",
            actions=[
                {
                    "link": {
                        "old": {"path": "modules/demo/source", "source_scope": "repo"}
                    }
                }
            ],
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertTrue(self.old.is_symlink())
        self.assertTrue(self.receipt.exists())

    def test_missing_download_is_pruned_and_legacy_receipt_is_upgraded(self) -> None:
        self.module(
            "demo",
            actions=[
                {
                    "download": {
                        "url": "https://example.com/tool",
                        "destination": "asset",
                    }
                }
            ],
        )
        with patch(
            "etchlib.providers.download.provider.download",
            side_effect=lambda transfer, path, **kwargs: path.write_bytes(b"asset"),
        ):
            self.assertTrue(
                apply_repository(load_repository(self.root), self.registry).succeeded
            )
        receipt = next((self.root / ".etch/downloads").glob("*.json"))
        data = json.loads(receipt.read_text())
        self.assertEqual(data["destination"], str(self.root / "asset"))
        del data["destination"]
        receipt.write_text(json.dumps(data))
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertEqual(
            json.loads(receipt.read_text())["destination"], str(self.root / "asset")
        )
        (self.root / "asset").unlink()
        self.module("demo", actions=[])
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertFalse(receipt.exists())

    def test_explicit_clean_removes_matching_receipt(self) -> None:
        self.setup_link()
        self.module(
            "demo",
            actions=[
                {"clean": {"paths": [str(self.root)], "obsolete": [str(self.old)]}}
            ],
        )
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertFalse(self.old.is_symlink())
        self.assertFalse(self.receipt.exists())

    def test_missing_outputs_prune_records_and_do_not_touch_unrelated_files(
        self,
    ) -> None:
        self.setup_link()
        self.old.unlink()
        directory = self.receipt.parent
        (directory / "bad.json").write_text("bad JSON")
        (directory / "empty.json").write_text("{}")
        (directory / "notes.txt").write_text("leave alone")
        self.module("demo", actions=[])
        report = apply_repository(load_repository(self.root), self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertEqual([p.name for p in directory.iterdir()], ["notes.txt"])

    def test_configuration_and_refreshed_records_are_rechecked(self) -> None:
        from etchlib.execution.housekeeping import finish
        from etchlib.execution.results import ExecutionReport
        from etchlib.providers.filesystem.receipts import record

        self.setup_link()
        self.module("demo", actions=[])
        repository = load_repository(self.root)
        plan = plan_repository(repository, self.registry)
        record(self.root, self.old, "demo")
        result = finish(repository, ExecutionReport((), {}), plan)
        self.assertTrue(result.succeeded, result.error)
        self.assertTrue(self.old.is_symlink())
        self.module("demo", actions=[{"create": ["new"]}])
        result = finish(repository, ExecutionReport((), {}), plan)
        self.assertFalse(result.succeeded)
        self.assertIn("configuration changed", result.error or "")
        self.assertTrue(self.old.is_symlink())

    def test_incomplete_module_directory_and_conditioned_declarations_are_preserved(
        self,
    ) -> None:
        self.setup_link()
        self.module(
            "demo", actions=[{"link": {"old": "source"}, "when": {"os": "nonexistent"}}]
        )
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertTrue(self.old.is_symlink())
        (self.root / "modules/demo/module.conf").unlink()
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertTrue(self.old.is_symlink())

    def test_partial_runs_preserve_removed_modules_until_a_full_run(self) -> None:
        self.setup_link()
        self.module("other", actions=[])
        shutil.rmtree(self.root / "modules/demo")
        self.assertTrue(
            apply_repository(
                load_repository(self.root, selected=["other"]), self.registry
            ).succeeded
        )
        self.assertTrue(self.old.is_symlink())
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertFalse(self.old.is_symlink())

    def test_repository_without_a_complete_catalog_cannot_retire_links(self) -> None:
        from etchlib.config import Repository

        self.setup_link()
        self.module("demo", actions=[])
        self.module("other", actions=[{"link": {"old": "source"}}])
        selected = load_repository(self.root, selected=["demo"])
        repository = Repository(selected.root, selected.modules, selected.defaults)
        report = apply_repository(repository, self.registry)
        self.assertTrue(report.succeeded, report.error)
        self.assertTrue(self.old.is_symlink())
        self.assertTrue(self.receipt.exists())

    def test_temporary_download_data_is_released_on_failure(self) -> None:
        self.module(
            "demo",
            actions=[
                {
                    "download": {
                        "url": "https://example.com/tool",
                        "destination": "asset",
                    }
                }
            ],
        )

        def fail(transfer: Any, path: Path, **kwargs: Any) -> None:
            path.write_bytes(b"partial data")
            raise OSError("interrupted transfer")

        with patch("etchlib.providers.download.provider.download", side_effect=fail):
            report = apply_repository(load_repository(self.root), self.registry)
        self.assertFalse(report.succeeded)
        self.assertFalse((self.root / "asset").exists())
        self.assertEqual(list(self.root.glob(".etch-download-*")), [])

    def test_legacy_orphaned_download_metadata_is_pruned_only_on_full_runs(
        self,
    ) -> None:
        import hashlib

        self.module("demo", actions=[])
        directory = self.root / ".etch/downloads"
        directory.mkdir(parents=True)
        receipt = directory / ("0" * 64 + ".json")
        receipt.write_text(
            json.dumps(
                {
                    "module": "deleted",
                    "url": "https://example.com/tool",
                    "sha256": hashlib.sha256(b"asset").hexdigest(),
                }
            )
        )
        self.assertTrue(
            apply_repository(
                load_repository(self.root, selected=["demo"]), self.registry
            ).succeeded
        )
        self.assertTrue(receipt.exists())
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertFalse(receipt.exists())

    def test_changed_configuration_before_planning_does_not_authorize_retirement(
        self,
    ) -> None:
        self.setup_link()
        self.module("demo", actions=[])
        repository = load_repository(self.root)
        self.module("other", actions=[{"link": {"old": "source"}}])
        report = apply_repository(repository, self.registry)
        self.assertFalse(report.succeeded)
        self.assertIn("configuration changed", report.error or "")
        self.assertTrue(self.old.is_symlink())

    def test_sparse_omission_is_not_a_removed_module(self) -> None:
        self.setup_link()

        def git(*args: str) -> None:
            subprocess.run(
                ["git", "-C", str(self.root), *args], capture_output=True, check=True
            )

        git("init", "-q")
        git("add", "modules")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "modules",
        )
        git(
            "update-index",
            "--skip-worktree",
            "modules/demo/module.conf",
            "modules/demo/source",
        )
        shutil.rmtree(self.root / "modules/demo")
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertTrue(self.old.is_symlink())
        git(
            "update-index",
            "--no-skip-worktree",
            "modules/demo/module.conf",
            "modules/demo/source",
        )
        self.assertTrue(
            apply_repository(load_repository(self.root), self.registry).succeeded
        )
        self.assertFalse(self.old.is_symlink())

    def test_final_ineligible_selection_preserves_retirement_candidate(self) -> None:
        self.setup_link()
        self.module("demo", actions=[])
        repository = load_repository(self.root)
        report = plan_repository(repository, self.registry)
        for selection in (
            Selection(Result(Outcome.FALSE), ()),
            Selection(Result(Outcome.TRUE), (Result(Outcome.DEFERRED),)),
        ):
            final = replace(report, selections={"demo": selection})
            result = finish(repository, ExecutionReport((), {}), final)
            self.assertTrue(result.succeeded)
            self.assertTrue(self.old.is_symlink())
            self.assertTrue(self.receipt.exists())
