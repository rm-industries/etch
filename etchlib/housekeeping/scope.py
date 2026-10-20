"""Establish current declaration authority without inventory or network probes."""

import shutil
import subprocess
from pathlib import Path

from etchlib.config import Repository, load_repository
from etchlib.providers.filesystem.state import kind


def configuration(root: Path) -> tuple[tuple[Path, bytes], ...]:
    paths = sorted((root / "modules").glob("*/module.conf")) + sorted(
        (root / "profiles").glob("*.conf")
    )
    if (root / "defaults.conf").exists():
        paths.append(root / "defaults.conf")
    return tuple((path, path.read_bytes()) for path in paths)


def checked_configuration(repository: Repository) -> tuple[tuple[Path, bytes], ...]:
    snapshot = configuration(repository.root)
    if repository.catalog is not None:
        current = load_repository(
            repository.root,
            profile=repository.profile,
            selected=None
            if repository.full_selection or repository.profile is not None
            else [module.name for module in repository.modules],
        )
        if (
            current.catalog != repository.catalog
            or current.modules != repository.modules
            or current.defaults != repository.defaults
            or configuration(repository.root) != snapshot
        ):
            raise ValueError(
                "configuration changed since loading; automatic cleanup deferred"
            )
    return snapshot


def removed_module(root: Path, name: str) -> bool:
    if kind(root / "modules" / name) != "missing":
        return False
    if not any((parent / ".git").exists() for parent in (root, *root.parents)):
        return not (root / ".gitmodules").exists()
    if shutil.which("git") is None:
        return False
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-t",
                "--stage",
                "--",
                "modules/" + name,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    # Sparse exclusions and uninitialized gitlinks do not remove declarations.
    return result.returncode == 0 and not any(
        line.startswith("S ") or line[2:].startswith("160000 ")
        for line in result.stdout.splitlines()
    )
