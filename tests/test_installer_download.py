import socket
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tests.installer_fixtures import InstallerFixture


class DownloadTests(InstallerFixture):
    def test_tls_verification_and_per_download_override(self) -> None:
        with self.assertRaises(URLError):
            self.apply(self.plan(tls={}))
        insecure = self.plan(tls={"verify": False})
        self.assertIn("TLS verification disabled", insecure.description)
        self.assertTrue(self.apply(insecure).changed)
        (self.root / "installed").unlink()
        with self.assertRaises(URLError):
            self.apply(self.plan(tls={}))
        self.assertTrue(self.apply(self.plan()).changed)

    def test_checksum_mismatch_never_executes(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.apply(self.plan(sha256="0" * 64))
        self.assertFalse((self.root / "installed").exists())
        self.assertEqual(self.server.requests, ["/install"])

    def test_response_failures_never_execute(self) -> None:
        for status, headers, body in [
            (500, {}, self.server.body),
            (206, {}, self.server.body),
            (200, {}, b""),
            (200, {"Content-Type": "text/html"}, b"<html>error</html>"),
            (200, {"Content-Length": "2000"}, self.server.body),
            (200, {"Content-Length": "invalid"}, self.server.body),
            (200, {"Content-Encoding": "gzip"}, self.server.body),
        ]:
            with self.subTest(status=status, headers=headers):
                self.server.status, self.server.headers, self.server.body = (
                    status,
                    headers,
                    body,
                )
                with self.assertRaises((ValueError, HTTPError)):
                    self.apply(self.plan())
                self.assertFalse((self.root / "installed").exists())
        self.assertEqual(len(self.server.requests), 7)

    def test_redirects_are_not_followed(self) -> None:
        for status in (301, 302, 303, 307, 308):
            self.server.status = status
            self.server.headers = {"Location": self.url + "-redirected"}
            with (
                self.subTest(status=status),
                self.assertRaises((ValueError, HTTPError)),
            ):
                self.apply(self.plan())
        self.assertEqual(self.server.requests, ["/install"] * 5)

    def test_size_limit_is_enforced(self) -> None:
        with patch("etchlib.providers.installer.download.MAX_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "Content-Length"):
                self.apply(self.plan())
            self.server.omit_length = True
            with self.assertRaisesRegex(ValueError, "download limit"):
                self.apply(self.plan())
        self.assertFalse((self.root / "installed").exists())

    def test_download_timeout_has_no_retry(self) -> None:
        self.server.delay = 0.2
        with self.assertRaises((socket.timeout, URLError)):
            self.apply(self.plan(download_timeout=0.05))
        self.assertLessEqual(len(self.server.requests), 1)
        self.assertFalse((self.root / "installed").exists())
