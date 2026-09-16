"""Command presence, application version, and normalized extension inventory."""

from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactResult, FactState
from etchlib.versions.parser import extract_version

from .cli import installed, locate, run
from .schema import target


class VSCodeFact:
    def __init__(self, kind: str) -> None:
        if kind not in ("command", "version", "extensions"):
            raise ValueError("unsupported VS Code fact")
        self.kind = kind
        self.name = "vscode." + kind

    def validate(self, config: Any, context: Context) -> None:
        target(config)

    def gather(self, config: Any, context: Context) -> FactResult:
        options = target(config)
        executable = locate(options, context)
        if executable is None:
            return FactResult(
                FactState.UNAVAILABLE,
                reason="VS Code command {!r} not found or not executable".format(
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
        return FactResult(
            FactState.VALUE, list(installed(executable, options, context))
        )
