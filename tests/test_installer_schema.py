from typing import Any

from etchlib.providers.errors import ProviderError
from tests.installer_fixtures import InstallerFixture


class InstallerSchemaTests(InstallerFixture):
    def test_invalid_options_fail_before_network(self) -> None:
        invalid: list[dict[str, Any]] = [
            {"url": "http://example.com/install"},
            {"url": "file:///tmp/install"},
            {"url": "https://user:secret@example.com/install"},
            {"url": "https://example.com/#fragment"},
            {"url": "https://example.com/\ninstall"},
            {"url": "https://example.com:99999/install"},
            {"sha256": "bad"},
            {"tls": {"verify": "no"}},
            {"tls": {"unknown": True}},
            {"tls": {"verify": False, "ca_file": "ca.pem"}},
            {"tls": {"ca_file": "../outside"}},
            {"tls": {"ca_file": "missing.pem"}},
            {"args": "--yes"},
            {"shell": ""},
            {"timeout": False},
            {"download_timeout": 0},
            {"download_timeout": float("inf")},
            {"retries": 1},
            {"check": {"shell": "true"}},
            {"env": {"BAD=NAME": "x"}},
        ]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ProviderError):
                self.plan(**options)
        self.assertEqual(self.server.requests, [])
