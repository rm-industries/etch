"""Filesystem state inspection shared by core providers."""

import stat
from pathlib import Path


def kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "missing"
    if stat.S_ISLNK(mode):
        return "link"
    return "directory" if stat.S_ISDIR(mode) else "file"


def check_parent(path: Path, create: bool) -> None:
    parent = path.parent
    while kind(parent) == "missing":
        if not create:
            raise ValueError(
                "missing parent directory: {} (enable create)".format(parent)
            )
        parent = parent.parent
    if not parent.is_dir():
        raise ValueError("parent is not a directory: {}".format(parent))


def directory_needed(path: Path) -> bool:
    state = kind(path)
    if state == "directory" or (state == "link" and path.is_dir()):
        return False
    if state != "missing":
        raise ValueError("refusing to replace non-directory: {}".format(path))
    check_parent(path, True)
    return True
