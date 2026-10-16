"""Read ownership records once and remove only the version that was inspected."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

from etchlib.providers.filesystem.state import kind


def filename(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest() + ".json"


def stamp(path: Path) -> tuple[int, int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino, info.st_ctime_ns


@dataclass(frozen=True)
class Record:
    path: Path
    raw: bytes
    version: tuple[int, int, int]
    data: Optional[dict[str, Any]]

    def current(self) -> bool:
        return (
            kind(self.path) == "file"
            and stamp(self.path) == self.version
            and self.path.read_bytes() == self.raw
        )

    def forget(self) -> bool:
        if not self.current():
            return False
        self.path.unlink()
        return True

    def upgrade(self, target: Path) -> bool:
        if not self.current():
            return False
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(
                    dict(self.data or {}, destination=str(target)),
                    stream,
                    sort_keys=True,
                )
            if not self.current():
                return False
            os.replace(temporary, self.path)
            return True
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def records(root: Path, namespace: str) -> Iterator[Record]:
    directory = root / ".etch" / namespace
    for parent in (directory.parent, directory):
        state = kind(parent)
        if state == "missing":
            return
        if state != "directory":
            raise ValueError(
                "ownership receipt directory must be a real directory: {}".format(
                    parent
                )
            )
    for path in sorted(directory.glob("*.json")):
        if kind(path) != "file":
            continue
        version = stamp(path)
        raw = path.read_bytes()
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            data = None
        yield Record(path, raw, version, data if isinstance(data, dict) else None)
