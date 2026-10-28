"""Explicit command, version and global package inventory facts."""

from typing import Any

from etchlib.providers import native
from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactResult, FactState
from etchlib.versions.parser import extract_version

from .cli import global_prefix, installed, run
from .schema import target


class NpmFact:
    def __init__(self, kind: str) -> None:
        if kind not in ("command", "version", "packages"):
            raise ValueError("unsupported npm fact")
        self.kind, self.name = kind, "npm." + kind

    def validate(self, config: Any, context: Context) -> None:
        target(config, context)

    def gather(self, config: Any, context: Context) -> FactResult:
        options = target(config, context)
        executable = native.locate(options.command, context.module_root)
        if executable is None:
            return FactResult(
                FactState.UNAVAILABLE,
                reason="npm command {!r} not found or not executable".format(
                    options.command
                ),
            )
        if self.kind == "command":
            return FactResult(FactState.VALUE, executable)
        if self.kind == "version":
            return FactResult(
                FactState.VALUE,
                extract_version(run(executable, options, ("--version",), context)),
            )
        prefix = global_prefix(executable, options, context)
        return FactResult(
            FactState.VALUE, list(installed(executable, options, prefix, context))
        )
