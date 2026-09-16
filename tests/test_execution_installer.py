from etchlib.config import Module, Repository
from etchlib.execution.results import Status
from etchlib.execution.runner import apply_repository
from tests.installer_fixtures import InstallerFixture


class StagedInstallerTests(InstallerFixture):
    def repository(self) -> Repository:
        return Repository(
            self.root,
            (
                Module(
                    "demo",
                    self.root,
                    {
                        "facts": {
                            "starship_version": {
                                "version": {"command": ["./starship", "--version"]}
                            }
                        },
                        "actions": [
                            {"installer": self.config, "refresh": ["starship_version"]},
                            {
                                "link": {
                                    str(self.root / "home-config"): "generated-config"
                                },
                                "when": {
                                    "fact": {
                                        "name": "starship_version",
                                        "matches": ">=1.0",
                                    }
                                },
                            },
                        ],
                    },
                ),
            ),
            {},
        )

    def test_fresh_install_refresh_configure_and_idempotent_second_apply(self) -> None:
        self.server.body = b"""from pathlib import Path
binary = Path('starship')
binary.write_text('#!/bin/sh\\nprintf "starship 1.2.3\\\\n"\\n')
binary.chmod(0o755)
Path('generated-config').write_text('configuration')
Path('installed').touch()
"""
        first = apply_repository(self.repository(), self.registry)
        self.assertTrue(first.succeeded, first.error)
        self.assertEqual(
            [result.status for result in first.actions],
            [Status.CHANGED, Status.CHANGED],
        )
        self.assertEqual((self.root / "home-config").read_text(), "configuration")
        self.assertEqual(self.server.requests, ["/install"])
        second = apply_repository(self.repository(), self.registry)
        self.assertTrue(second.succeeded, second.error)
        self.assertEqual(
            [result.status for result in second.actions],
            [Status.SKIPPED, Status.SKIPPED],
        )
        self.assertEqual(self.server.requests, ["/install"])

    def test_failed_installer_blocks_configuration(self) -> None:
        self.server.body = b"raise SystemExit(3)\n"
        report = apply_repository(self.repository(), self.registry)
        self.assertFalse(report.succeeded)
        self.assertEqual(
            [result.status for result in report.actions],
            [Status.FAILED, Status.BLOCKED],
        )
        self.assertFalse((self.root / "home-config").exists())

    def test_installer_success_without_tool_is_a_resolution_failure(self) -> None:
        self.server.body = b"pass\n"
        report = apply_repository(self.repository(), self.registry)
        self.assertFalse(report.succeeded)
        self.assertIn("unresolved condition", report.error or "")
        self.assertEqual(
            [result.status for result in report.actions],
            [Status.CHANGED, Status.BLOCKED],
        )
        self.assertFalse((self.root / "home-config").exists())
