"""Command, version and installed user tool inventory facts."""

from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactResult, FactState
from etchlib.versions.parser import extract_version

from .cli import capture, directories, installed, locate
from .schema import target


class UvFact:
    def __init__(self, kind: str) -> None:
        if kind not in ("command", "version", "tools"):
            raise ValueError("unsupported uv fact")
        self.kind, self.name = kind, "uv." + kind

    def validate(self, config: Any, context: Context) -> None:
        target(config)

    def gather(self, config: Any, context: Context) -> FactResult:
        options = target(config)
        executable = locate(options, context)
        if executable is None:
            return FactResult(
                FactState.UNAVAILABLE,
                reason="uv command {!r} not found or not executable".format(
                    options.command
                ),
            )
        if self.kind == "command":
            return FactResult(FactState.VALUE, executable)
        if self.kind == "version":
            return FactResult(
                FactState.VALUE,
                extract_version(
                    capture(executable, options, ("--version",), context).stdout
                ),
            )
        paths = directories(executable, options, context)
        return FactResult(
            FactState.VALUE, list(installed(executable, options, paths, context))
        )
