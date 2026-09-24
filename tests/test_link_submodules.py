"""Submodule-backed link sources are validated without changing Git state."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from etchlib.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import Plan, PlanStatus


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class LinkSubmoduleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        plugin = self.root / "plugin"
        plugin.mkdir()
        git(plugin, "init", "-q")
        git(
            plugin,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "plugin",
        )
        repo = self.root / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        self.module = repo / "modules" / "vim"
        self.module.mkdir(parents=True)
        git(
            repo,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(plugin),
            "modules/vim/bundle/plugin",
        )
        git(
            repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qam",
            "add plugin",
        )
        self.source = self.module / "bundle"
        self.target = self.root / "home" / ".vim"
        self.target.parent.mkdir()
        self.context = Context(repo, self.module, "vim", {})
        self.action = core_registry().action("link")
        self.config = {str(self.target): "bundle"}

    def plan(self) -> Plan:
        return plan_action(self.action, self.config, self.context)

    def test_uninitialized_submodule_is_diagnosed_without_mutation(self) -> None:
        git(self.context.repo_root, "submodule", "deinit", "-f", "--all")
        with self.assertRaisesRegex(
            ProviderError, "git submodule update --init --recursive"
        ) as error:
            self.plan()
        self.assertIn("modules/vim/bundle/plugin", str(error.exception))
        self.assertFalse(self.target.exists())
        self.assertFalse((self.source / "plugin" / ".git").exists())

    def test_initialized_link_conflict_and_idempotence(self) -> None:
        plan = self.plan()
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertTrue(self.action.provider.apply(plan, self.context).changed)
        self.assertEqual(self.plan().status, PlanStatus.SKIP)
        self.assertFalse(self.action.provider.apply(plan, self.context).changed)
        self.target.unlink()
        self.target.write_text("preserve")
        with self.assertRaises(ProviderError):
            self.plan()
        self.assertEqual(self.target.read_text(), "preserve")

    def test_wrong_revision_is_reported(self) -> None:
        plugin = self.root / "plugin"
        git(
            plugin,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "new revision",
        )
        git(self.source / "plugin", "fetch", "-q", str(plugin), "HEAD")
        git(self.source / "plugin", "checkout", "-q", "FETCH_HEAD")
        with self.assertRaisesRegex(ProviderError, "pinned revision") as error:
            self.plan()
        self.assertIn("modules/vim/bundle/plugin", str(error.exception))


if __name__ == "__main__":
    unittest.main()
