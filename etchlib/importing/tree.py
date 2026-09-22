"""Validate Git entries and copy raw blobs without archive/path extraction."""

import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .git import Git
from .source import relative

MAX_FILES = 10_000
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024


@dataclass(frozen=True)
class Entry:
    path: str
    oid: str
    size: int
    executable: bool


def entries(git: Git, commit: str, path: str) -> tuple[Entry, ...]:
    tree = git.run("ls-tree", "-z", commit, "--", path)
    fields = tree.rstrip(b"\0").split(b"\t", 1)
    if (
        len(fields) != 2
        or not fields[0].startswith(b"040000 tree ")
        or fields[1].decode("utf-8") != path
    ):
        raise ValueError("source path is not a Git directory")
    oid = fields[0].split()[2].decode("ascii")
    raw = git.run("ls-tree", "-r", "-z", oid)
    result: list[Entry] = []
    seen: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, filename = record.split(b"\t", 1)
        mode, kind, blob = metadata.split()
        name = filename.decode("utf-8", errors="strict")
        parts = relative(name)
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ValueError(
                "unsupported Git entry {!r}: symlinks/submodules are not imported".format(
                    name
                )
            )
        if len(parts) == 1 and name.casefold() == ".etch-import.json":
            raise ValueError("upstream .etch-import.json is reserved")
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = unicodedata.normalize("NFC", prefix).casefold()
            if key in seen and seen[key] != prefix:
                raise ValueError("case/normalization collision at {!r}".format(prefix))
            seen[key] = prefix
        if len(result) >= MAX_FILES:
            raise ValueError("selected module exceeds import file/byte limits")
        if not re.fullmatch(rb"[0-9a-f]{40}", blob):
            raise ValueError("invalid Git blob identity")
        result.append(Entry(name, blob.decode("ascii"), 0, mode == b"100755"))
    if not any(entry.path == "module.conf" for entry in result):
        raise ValueError("source module is missing module.conf")
    # Request wanted blobs together, rather than triggering one lazy fetch per
    # object while querying sizes. Explicit blob wants do not fetch sibling assets.
    objects = list(dict.fromkeys(entry.oid for entry in result))
    for offset in range(0, len(objects), 256):
        git.run(
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            "origin",
            *objects[offset : offset + 256],
        )
    sizes = git.run(
        "cat-file",
        "--batch-check",
        input_data="".join(entry.oid + "\n" for entry in result).encode("ascii"),
    ).splitlines()
    if len(sizes) != len(result):
        raise ValueError("Git returned incomplete blob sizes")
    sized = []
    total = 0
    for entry, raw_size in zip(result, sizes):
        blob_id, kind, count = raw_size.split()
        size = int(count)
        if blob_id.decode("ascii") != entry.oid or kind != b"blob" or size < 0:
            raise ValueError("Git returned invalid blob metadata")
        total += size
        if size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("selected module exceeds import file/byte limits")
        sized.append(Entry(entry.path, entry.oid, size, entry.executable))
    return tuple(sized)


def materialize(git: Git, selected: tuple[Entry, ...], destination: Path) -> None:
    # Batch lazy retrieval of selected objects; outputs go to disk, not memory.
    with tempfile.TemporaryFile() as stream:
        git.run(
            "cat-file",
            "--batch",
            input_data="".join(entry.oid + "\n" for entry in selected).encode("ascii"),
            output=stream,
        )
        stream.seek(0)
        for entry in selected:
            expected = "{} blob {}\n".format(entry.oid, entry.size).encode("ascii")
            if stream.readline(256) != expected:
                raise ValueError("Git returned unexpected blob metadata")
            data = stream.read(entry.size)
            if len(data) != entry.size or stream.read(1) != b"\n":
                raise ValueError("Git returned truncated blob content")
            if data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                raise ValueError(
                    "LFS pointer {!r}: supply ordinary module assets".format(entry.path)
                )
            target = destination / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as file:
                file.write(data)
            target.chmod(0o755 if entry.executable else 0o644)
        if stream.read(1):
            raise ValueError("unexpected extra Git blob data")
