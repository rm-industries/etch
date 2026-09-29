"""The managed download action places upstream bytes without executing them."""

import hashlib
from typing import Any
from urllib.error import HTTPError

from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus
from tests.installer_fixtures import InstallerFixture


class DownloadActionTests(InstallerFixture):
    def setUp(self) -> None:
        super().setUp()
        self.server.body = b"not a shell script\n"
        self.target = self.root / "nested" / "autoload" / "plug.vim"
        self.config = {
            "url": self.url,
            "destination": str(self.target),
            "tls": {"ca_file": "ca.pem"},
            "check": {"file_exists": str(self.target)},
        }

    def plan(self, **options: Any) -> Plan:
        return plan_action(
            self.registry.action("download"),
            dict(self.config, **options),
            self.context,
        )

    def apply(self, plan: Plan) -> ApplyResult:
        result = self.registry.action("download").provider.apply(plan, self.context)
        assert isinstance(result, ApplyResult)
        return result

    def test_plan_is_offline_and_second_apply_skips(self) -> None:
        plan = self.plan()
        self.assertEqual(plan.status, PlanStatus.CHANGE)
        self.assertTrue(plan.network)
        self.assertIn(str(self.target), plan.description)
        self.assertIn(self.url, plan.description)
        self.assertEqual(self.server.requests, [])
        self.assertFalse(self.target.parent.exists())
        self.assertTrue(self.apply(plan).changed)
        self.assertEqual(self.target.read_bytes(), self.server.body)
        self.assertEqual(self.server.requests, ["/install"])
        again = self.plan()
        self.assertEqual(again.status, PlanStatus.SKIP)
        self.assertFalse(again.network)
        self.assertFalse(self.apply(again).changed)
        self.assertEqual(self.server.requests, ["/install"])

    def test_existing_file_and_symlink_conflict_even_when_check_passes(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"user content")
        with self.assertRaisesRegex(ValueError, "unmanaged file"):
            self.plan()
        self.target.unlink()
        self.target.symlink_to(self.root / "ca.pem")
        with self.assertRaisesRegex(ValueError, "non-file"):
            self.plan()
        self.assertEqual(self.server.requests, [])

    def test_modified_managed_file_is_not_overwritten(self) -> None:
        self.apply(self.plan())
        self.target.write_bytes(b"user edit")
        with self.assertRaisesRegex(ValueError, "unmanaged file"):
            self.plan()
        self.assertEqual(self.target.read_bytes(), b"user edit")

    def test_failed_replacement_preserves_owned_file(self) -> None:
        self.apply(self.plan())
        original = self.target.read_bytes()
        self.server.body = b"new response"
        retry = self.plan(check={"file_exists": str(self.root / "absent")})
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.apply(
                self.plan(
                    check={"file_exists": str(self.root / "absent")},
                    sha256="0" * 64,
                )
            )
        self.assertEqual(retry.status, PlanStatus.CHANGE)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(list(self.target.parent.glob(".etch-download-*")), [])

    def test_failed_fresh_transfer_leaves_no_file(self) -> None:
        self.server.status = 500
        with self.assertRaises((ValueError, HTTPError)):
            self.apply(self.plan())
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.glob(".etch-download-*")), [])

    def test_pinned_content_and_changed_source(self) -> None:
        checksum = hashlib.sha256(self.server.body).hexdigest()
        self.apply(self.plan(sha256=checksum))
        self.assertEqual(self.plan(sha256=checksum).status, PlanStatus.SKIP)
        self.assertEqual(self.plan(sha256="0" * 64).status, PlanStatus.CHANGE)
        self.server.body = b"replacement"
        changed = self.plan(
            url=self.url + "?version=2", check={"file_exists": str(self.target)}
        )
        self.assertEqual(changed.status, PlanStatus.CHANGE)
        self.apply(changed)
        self.assertEqual(self.target.read_bytes(), b"replacement")
