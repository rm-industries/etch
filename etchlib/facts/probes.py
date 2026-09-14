"""Local command, environment and filesystem observations; never run a shell."""
import os
from pathlib import Path
import shutil
import stat

from etchlib.providers.observations import FactResult, FactState


class LocalProbe:
    def __init__(self, name):
        self.name = name

    def validate(self, config, context):
        if not isinstance(config, str) or not config or "\x00" in config:
            raise ValueError("{} expects a nonempty string".format(self.name))

    def gather(self, config, context):
        try:
            if self.name in ("command", "command_path"):
                command = config
                if "/" in config:
                    command_path = Path(config).expanduser()
                    if not command_path.is_absolute():
                        command_path = context.module_root / command_path
                    command = str(command_path)
                found = shutil.which(command)
                if found is None:
                    return FactResult(FactState.UNAVAILABLE, reason="command {!r} not found".format(config))
                return FactResult(FactState.VALUE, True if self.name == "command" else os.path.abspath(found))
            if self.name == "env":
                if config not in os.environ:
                    return FactResult(FactState.UNAVAILABLE, reason="environment variable {!r} is unset".format(config))
                return FactResult(FactState.VALUE, os.environ[config])
            path = Path(config).expanduser()
            if not path.is_absolute():
                path = context.module_root / path
            try:
                mode = path.stat().st_mode
            except (FileNotFoundError, NotADirectoryError):
                return FactResult(FactState.VALUE, False)
            matches = {"path_exists": True, "file_exists": stat.S_ISREG(mode),
                       "directory_exists": stat.S_ISDIR(mode)}
            return FactResult(FactState.VALUE, matches[self.name])
        except (OSError, RuntimeError, ValueError) as exc:
            return FactResult(FactState.ERROR, reason="{} {!r}: {}".format(self.name, config, exc))
