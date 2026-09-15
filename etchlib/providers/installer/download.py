"""Bounded HTTPS downloads with request-local TLS and no automatic redirects."""

import hashlib
import ssl
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Optional
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .schema import Installer

MAX_BYTES = 8 * 1024 * 1024


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Optional[Request]:
        fp.close()
        raise ValueError("installer redirects are not allowed; use the final HTTPS URL")


def download(installer: Installer, destination: Path) -> None:
    context = ssl.create_default_context()
    if installer.ca_file is not None:
        context.load_verify_locations(cafile=str(installer.ca_file))
    if not installer.verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=context), NoRedirects())
    request = Request(
        installer.url,
        headers={"User-Agent": "Etch installer", "Accept-Encoding": "identity"},
    )
    digest = hashlib.sha256()
    size = 0
    try:
        response = opener.open(request, timeout=installer.download_timeout)
    except HTTPError as exc:
        exc.close()
        raise ValueError("installer download failed: HTTP {}".format(exc.code)) from exc
    with response:
        if response.status != 200:
            raise ValueError("installer download requires HTTP 200")
        if response.headers.get_content_type() in (
            "text/html",
            "application/xhtml+xml",
        ):
            raise ValueError("installer download returned an HTML document")
        length = response.headers.get("Content-Length")
        if length is not None and (
            not length.isascii() or not length.isdigit() or int(length) > MAX_BYTES
        ):
            raise ValueError("invalid or excessive installer Content-Length")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("encoded installer responses are not supported")
        with destination.open("xb") as stream:
            while True:
                chunk = response.read(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("installer exceeds 8 MiB download limit")
                digest.update(chunk)
                stream.write(chunk)
    if not size or (length is not None and size != int(length)):
        raise ValueError("installer download is empty or truncated")
    if installer.sha256 is not None and digest.hexdigest() != installer.sha256:
        raise ValueError("installer SHA-256 mismatch")
