"""Update the consumer with Git policy, then align its recorded submodule pins."""

import subprocess
from pathlib import Path

from etchlib.submodules import require_root
from etchlib.submodules import update as update_submodules


def update(root: Path) -> int:
    root = require_root(root, "update")
    pulled = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "pull",
            "--ff-only",
            "--no-rebase",
            "--autostash",
            "--no-recurse-submodules",
        ],
        check=False,
        shell=False,
    )
    if pulled.returncode:
        return pulled.returncode
    # Git can return success after autostash restoration leaves conflicts.
    try:
        conflicts = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=U", "-z"],
            capture_output=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(
            "Timed out checking update conflicts; inspect the consumer checkout before retrying"
        ) from error
    if conflicts.returncode:
        return conflicts.returncode
    if conflicts.stdout:
        raise ValueError(
            "Local edits could not be restored cleanly; resolve Git conflicts before synchronizing submodules."
        )
    return update_submodules(root)
