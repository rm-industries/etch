import hashlib
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import PlanStatus
from tests.installer_fixtures import InstallerFixture


class InstallerTests(InstallerFixture):
    def test_default_shell_installs_a_command_and_check_skips_later_runs(self) -> None:
        self.config.pop("shell")
        self.config["check"] = {"command": "example-tool"}
        self.config["env"] = {"PATH": str(self.root) + os.pathsep + os.defpath}
        self.server.body = (
            b"printf '#!/bin/sh\\nexit 0\\n' > example-tool\nchmod +x example-tool\n"
        )
        self.assertTrue(self.apply(self.plan()).changed)
        self.assertEqual(self.plan().status, PlanStatus.SKIP)
        self.assertEqual(self.server.requests, ["/install"])

    def test_plan_is_nonmutating_and_execution_is_idempotent(self) -> None:
        plan = self.plan(sha256=hashlib.sha256(self.server.body).hexdigest().upper())
        self.assertEqual(plan.status, PlanStatus.RUN)
        self.assertTrue(plan.network and plan.opaque)
        self.assertIn(self.url, plan.description)
        self.assertEqual(self.server.requests, [])
        self.assertFalse((self.root / "installed").exists())
        self.assertTrue(self.apply(plan).changed)
        self.assertEqual(self.server.requests, ["/install"])
        self.assertEqual(self.plan().status, PlanStatus.SKIP)
        self.assertFalse(self.apply(plan).changed)
        self.assertEqual(self.server.requests, ["/install"])

    def test_arguments_environment_and_configuration_ownership(self) -> None:
        self.server.body = b"""import os, sys
from pathlib import Path
assert sys.argv[1:] == ['--yes', 'argument with spaces']
assert os.environ['ETCH_MODULE'] == 'demo'
assert os.environ['PROFILE'] == os.devnull
assert Path.cwd() == Path(os.environ['ETCH_MODULE_DIR'])
Path('installed').write_text('software')
Path('download-path').write_text(__file__)
"""
        self.assertTrue(
            self.apply(
                self.plan(
                    args=["--yes", "argument with spaces"], env={"PROFILE": os.devnull}
                )
            ).changed
        )
        self.assertFalse(Path((self.root / "download-path").read_text()).exists())
        source = self.root / "shell-init"
        source.write_text("# Etch owns shell integration\n")
        target = self.root / "home" / ".shellrc"
        link = self.registry.action("link")
        plan = plan_action(
            link, {str(target): {"path": "shell-init", "create": True}}, self.context
        )
        link.provider.apply(plan, self.context)
        self.assertEqual(target.read_text(), source.read_text())
        self.assertEqual(plan.claims[0].path, target)
        self.assertEqual(self.plan().claims, ())

    def test_failure_cleans_up_and_does_not_retry(self) -> None:
        self.server.body = b"from pathlib import Path\nPath('download-path').write_text(__file__)\nraise SystemExit(7)\n"
        with self.assertRaisesRegex(ValueError, "status 7"):
            self.apply(self.plan())
        self.assertFalse(Path((self.root / "download-path").read_text()).exists())
        self.assertEqual(self.server.requests, ["/install"])

    def test_execution_timeout_cleans_up(self) -> None:
        self.server.body = b"from pathlib import Path\nimport time\nPath('download-path').write_text(__file__)\ntime.sleep(10)\n"
        with self.assertRaisesRegex(ValueError, "command timed out"):
            self.apply(self.plan(timeout=1))
        self.assertFalse(Path((self.root / "download-path").read_text()).exists())

    def test_privilege_and_interactive_metadata(self) -> None:
        plan = self.plan(sudo=True, stdin=True)
        self.assertTrue(plan.elevated)
        self.assertIn("stdin-interactive", plan.resources)
        self.assertIn("sudo-interactive", plan.resources)
        with self.assertRaisesRegex(ValueError, "not been authorized"):
            self.apply(plan)
        self.assertEqual(self.server.requests, [])

    def test_installer_defaults_are_separate_from_shell_defaults(self) -> None:
        self.context = replace(
            self.context,
            defaults={"installer": {"quiet": True}, "shell": {"sudo": True}},
        )
        plan = self.plan()
        self.assertFalse(plan.elevated)
        self.assertTrue(plan.payload.options["quiet"])
        self.assertFalse(self.plan(quiet=False).payload.options["quiet"])

    def test_failed_download_removes_temporary_file(self) -> None:
        paths: list[Path] = []

        def fail_download(installer: object, path: Path) -> None:
            paths.append(path)
            path.write_text("partial")
            raise ValueError("download failed")

        with patch(
            "etchlib.providers.installer.provider.download", side_effect=fail_download
        ):
            with self.assertRaisesRegex(ValueError, "download failed"):
                self.apply(self.plan())
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].parent.exists())
