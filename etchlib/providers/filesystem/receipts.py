"""Local provenance for links actually created by Etch."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def identity(path):
    info = path.lstat()
    if not path.is_symlink():
        return None
    return {"destination": str(path), "target": os.readlink(path),
            "device": info.st_dev, "inode": info.st_ino, "ctime_ns": info.st_ctime_ns}


def receipt_path(repo, path, create=False):
    directory = repo / ".etch" / "links"
    for component in (repo / ".etch", directory):
        if component.is_symlink():
            raise ValueError("receipt directory cannot be a symlink: {}".format(component))
        if create:
            component.mkdir(exist_ok=True)
    name = hashlib.sha256(str(path).encode("utf-8")).hexdigest() + ".json"
    return directory / name


def record(repo, path, module):
    proof = identity(path)
    if proof is None:
        raise ValueError("cannot record ownership of a non-link")
    proof.update(schema=1, module=module)
    target = receipt_path(repo, path, create=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(proof, stream, sort_keys=True)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def owned(repo, path):
    """Absent, stale or unreadable receipts provide no permission to remove."""
    try:
        target = receipt_path(repo, path)
        if target.is_symlink():
            return False
        proof = json.loads(target.read_text(encoding="utf-8"))
        current = identity(path)
        return (isinstance(proof, dict) and type(proof.get("schema")) is int and proof["schema"] == 1
                and isinstance(proof.get("module"), str) and current is not None
                and all(proof.get(key) == value for key, value in current.items()))
    except (OSError, ValueError, RuntimeError):
        return False
