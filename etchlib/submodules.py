"""Explicit setup delegation; never advance consumer gitlink pins."""

import shutil
import subprocess
from pathlib import Path


def update(root: Path) -> int:
    root = root.resolve()
    if shutil.which("git") is None:
        raise ValueError(
            "Git is required for submodules update; install Git and retry."
        )
    try:
        checkout = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("Timed out checking the consumer Git repository") from error
    if checkout.returncode or Path(checkout.stdout.strip()).resolve() != root:
        raise ValueError(
            "--repo must select the consumer Git repository root: {}".format(root)
        )
    result = subprocess.run(
        ["git", "-C", str(root), "submodule", "update", "--init", "--recursive"],
        check=False,
        shell=False,
    )
    return result.returncode
