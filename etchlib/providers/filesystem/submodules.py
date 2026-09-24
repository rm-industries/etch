"""Read-only validation of Git submodules inside linked source trees."""

import shutil
import subprocess
from pathlib import Path


def check_submodules(source: Path) -> None:
    if not source.is_dir():
        return
    if shutil.which("git") is None:
        if any(
            (parent / ".gitmodules").exists() for parent in (source, *source.parents)
        ):
            raise ValueError(
                "Git is required to inspect submodules in {}".format(source)
            )
        return
    root_result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if root_result.returncode:
        return
    root = Path(root_result.stdout.strip())
    relative = source.relative_to(root)
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "submodule",
            "status",
            "--recursive",
            "--",
            str(relative),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            "cannot inspect submodules in {}: {}".format(source, result.stderr.strip())
        )
    for line in result.stdout.splitlines():
        if line.startswith(("-", "+", "U")):
            path = line[42:].split(" (", 1)[0]
            raise ValueError(
                "submodule {} is missing, uninitialized, or not at its pinned revision; "
                "run git submodule update --init --recursive in {}".format(
                    root / path, root
                )
            )
