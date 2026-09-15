"""Execution context and presence checks shared by shell and script actions."""

import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, Mapping

from etchlib.facts.platform import PlatformProbe
from etchlib.providers.contracts import Context


def environment(options: Mapping[str, Any], context: Context) -> dict[str, str]:
    env = dict(os.environ)
    env.update(options.get("env", {}))
    env.update(
        ETCH_MODULE_DIR=str(context.module_root),
        ETCH_REPO_DIR=str(context.repo_root),
        ETCH_MODULE=context.module_name,
    )
    for name in ("os", "distro", "arch"):
        result = PlatformProbe(name).gather({}, context)
        env["ETCH_" + name.upper()] = result.value or ""
    return env


def checked(options: Mapping[str, Any], context: Context) -> bool:
    check = options.get("check")
    if check is None:
        return False
    name, value = next(iter(check.items()))
    if name == "command":
        env = environment(options, context)
        search_path = os.pathsep.join(
            str(context.module_root / p) if not os.path.isabs(p) else p
            for p in os.get_exec_path(env)
        )
        command = (
            str(context.module_root / value)
            if "/" in value and not os.path.isabs(value)
            else value
        )
        return shutil.which(command, path=search_path) is not None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = context.module_root / path
    try:
        mode = path.stat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return False
    return name == "path_exists" or (
        stat.S_ISREG(mode) if name == "file_exists" else stat.S_ISDIR(mode)
    )


def preflight(options: Mapping[str, Any], context: Context) -> None:
    if options["provider"] == "script":
        path = Path(options["argv"][0])
        path.resolve().relative_to(context.module_root.resolve())
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(
                "script must be an executable module-owned file: {}".format(path)
            )


def run(options: Mapping[str, Any], context: Context) -> None:
    argv = list(options["argv"])
    if options.get("sudo", False):
        if not context.elevation_allowed:
            raise ValueError("command privilege escalation has not been authorized")
        argv = ["sudo", "-E", "--"] + argv
    try:
        result = subprocess.run(
            argv,
            cwd=context.module_root,
            env=environment(options, context),
            stdin=None if options.get("stdin", False) else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL if options.get("quiet", False) else None,
            stderr=subprocess.DEVNULL if options.get("quiet", False) else None,
            timeout=options.get("timeout", 300),
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("command timed out") from exc
    if result.returncode:
        raise ValueError("command exited with status {}".format(result.returncode))
