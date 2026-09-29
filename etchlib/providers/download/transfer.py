"""Bounded HTTPS downloads with request-local TLS and no automatic redirects."""

import hashlib
import ssl
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Optional
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .schema import Transfer

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
        raise ValueError("download redirects are not allowed; use the final HTTPS URL")


def download(transfer: Transfer, destination: Path, label: str = "installer") -> None:
    context = ssl.create_default_context()
    if transfer.ca_file is not None:
        context.load_verify_locations(cafile=str(transfer.ca_file))
    if not transfer.verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=context), NoRedirects())
    request = Request(
        transfer.url,
        headers={
            "User-Agent": "Etch installer" if label == "installer" else "Etch download",
            "Accept-Encoding": "identity",
        },
    )
    digest = hashlib.sha256()
    size = 0
    try:
        response = opener.open(request, timeout=transfer.download_timeout)
    except HTTPError as exc:
        exc.close()
        raise ValueError("{} download failed: HTTP {}".format(label, exc.code)) from exc
    with response:
        if response.status != 200:
            raise ValueError("{} download requires HTTP 200".format(label))
        if response.headers.get_content_type() in (
            "text/html",
            "application/xhtml+xml",
        ):
            raise ValueError("{} download returned an HTML document".format(label))
        length = response.headers.get("Content-Length")
        if length is not None and (
            not length.isascii() or not length.isdigit() or int(length) > MAX_BYTES
        ):
            raise ValueError("invalid or excessive {} Content-Length".format(label))
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("encoded {} responses are not supported".format(label))
        with destination.open("xb") as stream:
            while True:
                chunk = response.read(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("{} exceeds 8 MiB download limit".format(label))
                digest.update(chunk)
                stream.write(chunk)
    if not size or (length is not None and size != int(length)):
        raise ValueError("{} download is empty or truncated".format(label))
    if transfer.sha256 is not None and digest.hexdigest() != transfer.sha256:
        raise ValueError("{} SHA-256 mismatch".format(label))
