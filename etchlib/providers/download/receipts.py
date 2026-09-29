"""Content-based ownership receipts for downloaded files."""

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from etchlib.providers.installer.download import MAX_BYTES


def _receipt(repo: Path, destination: Path, create: bool = False) -> Path:
    parent = repo / ".etch" / "downloads"
    for directory in (parent.parent, parent):
        if directory.is_symlink():
            raise ValueError("download receipt directory cannot be a symlink")
        if create:
            directory.mkdir(exist_ok=True)
    return parent / (hashlib.sha256(str(destination).encode()).hexdigest() + ".json")


def _digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def owned_asset(
    repo: Path, destination: Path, module: str
) -> Optional[Tuple[str, str]]:
    try:
        receipt = _receipt(repo, destination)
        if (
            receipt.is_symlink()
            or not destination.is_file()
            or destination.is_symlink()
            or destination.stat().st_size > MAX_BYTES
        ):
            return None
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if (
            isinstance(data, dict)
            and data.get("module") == module
            and isinstance(data.get("url"), str)
            and data.get("sha256") == _digest(destination)
        ):
            return str(data["url"]), str(data["sha256"])
    except (OSError, ValueError, RuntimeError):
        pass
    return None


def record(repo: Path, destination: Path, module: str, url: str) -> None:
    receipt = _receipt(repo, destination, create=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=receipt.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(
                {"module": module, "url": url, "sha256": _digest(destination)},
                stream,
            )
        temporary.replace(receipt)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
