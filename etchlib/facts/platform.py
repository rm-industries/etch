"""Stable machine properties, without external commands or third-party parsers."""
from pathlib import Path
import platform
import shlex

from etchlib.providers.observations import FactResult, FactState


def distro_id():
    for path in (Path("/etc/os-release"), Path("/usr/lib/os-release")):
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            key, separator, value = line.partition("=")
            if separator and key == "ID":
                parts = shlex.split(value, comments=True)
                if len(parts) != 1 or not parts[0]:
                    raise ValueError("{}: invalid distribution ID".format(path))
                return parts[0].lower()
        return None
    return None


class PlatformProbe:
    def __init__(self, name):
        self.name = name

    def validate(self, config, context):
        if config != {}:
            raise ValueError("{} expects an empty options dictionary".format(self.name))

    def gather(self, config, context):
        try:
            system = platform.system().lower()
            if self.name == "os":
                value = {"darwin": "macos"}.get(system, system)
            elif self.name == "arch":
                machine = platform.machine().lower()
                value = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
            else:
                value = distro_id() if system == "linux" else None
            if not value:
                return FactResult(FactState.UNAVAILABLE, reason="{} is not available on this machine".format(self.name))
            return FactResult(FactState.VALUE, value)
        except (OSError, UnicodeError, ValueError) as exc:
            return FactResult(FactState.ERROR, reason="{} probe failed: {}".format(self.name, exc))
