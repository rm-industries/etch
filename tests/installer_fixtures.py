"""Local HTTPS upstream; the checked-in key is exclusively a public test fixture."""

import os
import shutil
import ssl
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from etchlib.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.plans import ApplyResult, Plan

FIXTURES = Path(__file__).parent / "fixtures"


class Upstream(ThreadingHTTPServer):
    body = b"from pathlib import Path\nPath('installed').write_text('ready')\n"
    status = 200
    delay = 0.0
    omit_length = False

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.requests: list[str] = []
        super().__init__(("127.0.0.1", 0), Handler)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(
            FIXTURES / "installer-ca.pem", FIXTURES / "installer-key.pem"
        )
        self.socket = tls.wrap_socket(self.socket, server_side=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        upstream = cast(Upstream, self.server)
        upstream.requests.append(self.path)
        time.sleep(upstream.delay)
        try:
            self.send_response(upstream.status)
            headers = dict(upstream.headers)
            if not upstream.omit_length:
                headers.setdefault("Content-Length", str(len(upstream.body)))
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(upstream.body)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass  # Timeout tests deliberately close the client before its response.

    def log_message(self, format: str, *args: Any) -> None:
        pass


class InstallerFixture(unittest.TestCase):
    def setUp(self) -> None:
        proxy = patch.dict(os.environ, {"no_proxy": "127.0.0.1,localhost"})
        proxy.start()
        self.addCleanup(proxy.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        shutil.copy2(FIXTURES / "installer-ca.pem", self.root / "ca.pem")
        self.server = Upstream()
        thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        thread.start()

        def stop() -> None:
            self.server.shutdown()
            self.server.server_close()
            thread.join(timeout=5)

        self.addCleanup(stop)
        self.url = "https://127.0.0.1:{}/install".format(self.server.server_port)
        self.context = Context(self.root, self.root, "demo", {})
        self.registry = core_registry()
        self.config: dict[str, Any] = {
            "url": self.url,
            "shell": sys.executable,
            "tls": {"ca_file": "ca.pem"},
            "check": {"file_exists": "installed"},
        }

    def plan(self, **options: Any) -> Plan:
        return plan_action(
            self.registry.action("installer"),
            dict(self.config, **options),
            self.context,
        )

    def apply(self, plan: Plan) -> ApplyResult:
        result = self.registry.action("installer").provider.apply(plan, self.context)
        assert isinstance(result, ApplyResult)
        return result
