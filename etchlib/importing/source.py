"""Validate the deliberately small public Git source interface."""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from etchlib.config import names


def relative(value: str) -> tuple[str, ...]:
    parts = value.split("/")
    if (
        any(
            not part or part in (".", "..") or part.casefold() == ".git"
            for part in parts
        )
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError("unsafe import path {!r}".format(value))
    return tuple(parts)


@dataclass(frozen=True)
class Source:
    url: str
    ref: str
    path: str
    name: str


def parse(source: str, ref: str, path: str) -> Source:
    if source.startswith("github:"):
        match = re.fullmatch(r"github:([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)", source)
        if match is None or match[2] in (".", ".."):
            raise ValueError("expected github:OWNER/REPOSITORY")
        repository = match[2].removesuffix(".git")
        if not repository:
            raise ValueError("empty GitHub repository")
        source = "https://github.com/{}/{}.git".format(match[1], repository)
    url = urlsplit(source)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or "?" in source
        or "#" in source
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in source)
        or "\\" in source
    ):
        raise ValueError(
            "import source must be a public HTTPS Git URL without credentials, query or fragment"
        )
    if url.port == 0:
        raise ValueError("invalid HTTPS port")
    if ref != "HEAD" and not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        if (
            not ref.startswith(("refs/heads/", "refs/tags/"))
            or ref.endswith("/")
            or any(token in ref for token in ("..", "@{", "//"))
            or any(
                c.isspace() or ord(c) < 32 or ord(c) == 127 or c in "~^:?*[\\"
                for c in ref
            )
            or any(
                part.startswith(".") or part.endswith((".", ".lock"))
                for part in ref.split("/")
            )
        ):
            raise ValueError(
                "ref must be HEAD, refs/heads/NAME, refs/tags/NAME or a full SHA-1 commit"
            )
    parts = relative(path)
    name = PurePosixPath(path).name
    names([name], Path(path), "module name")
    return Source(source, ref, "/".join(parts), name)
