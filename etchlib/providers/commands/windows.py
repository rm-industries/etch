"""Explicit Windows invocation; never route argument lists through cmd.exe."""

import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from etchlib.providers.contracts import Context


def invocation(
    options: Mapping[str, Any], context: Context, env: Mapping[str, str]
) -> list[str]:
    if options.get("sudo", False):
        raise ValueError(
            "sudo is not supported on Windows; run with the required account privileges"
        )
    argv = list(options["argv"])
    if options["provider"] == "script" and Path(argv[0]).suffix.lower() == ".ps1":
        argv = ["pwsh", "-NoProfile", "-NonInteractive", "-File"] + argv
    search = os.pathsep.join(
        str(context.module_root / entry) if not os.path.isabs(entry) else entry
        for entry in os.get_exec_path(env)
    )
    executable = argv[0]
    if ("/" in executable or os.sep in executable) and not os.path.isabs(executable):
        executable = str(context.module_root / executable)
    found = shutil.which(executable, path=search)
    if found is None:
        raise ValueError(
            "Windows executable {!r} not found; PowerShell scripts require PowerShell 7 (pwsh) on PATH".format(
                argv[0]
            )
        )
    if Path(found).suffix.lower() not in (".exe", ".com"):
        raise ValueError(
            "Windows commands require native .exe/.com executables; use a .ps1 script for PowerShell, not batch files"
        )
    argv[0] = os.path.abspath(found)
    return argv
