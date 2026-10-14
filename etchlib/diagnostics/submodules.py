"""Read-only repository-wide checks before loading consumer modules or plugins."""

import shutil
import subprocess
from pathlib import Path


def submodule_errors(root: Path) -> tuple[str, ...]:
    if not (root / ".gitmodules").is_file():
        return ()
    if shutil.which("git") is None:
        return ()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "submodule", "status", "--recursive"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return ("Cannot inspect repository submodules: {}".format(error),)
    if result.returncode:
        return (
            "Cannot inspect repository submodules: {}".format(result.stderr.strip()),
        )
    errors = []
    for line in result.stdout.splitlines():
        if line.startswith(("-", "+", "U")):
            path = line[1:].split(" ", 1)[1].split(" (", 1)[0]
            reason = {
                "-": "missing or uninitialized",
                "+": "not at its pinned revision",
                "U": "has an unresolved merge conflict",
            }[line[0]]
            errors.append(
                "Submodule {} {}. Run git submodule update --init --recursive in {}{}.".format(
                    path,
                    reason,
                    root,
                    " after resolving the conflict" if line[0] == "U" else "",
                )
            )
    return tuple(errors)
