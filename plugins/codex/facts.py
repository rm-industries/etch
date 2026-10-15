"""Read-only native command, version and user plugin inventories."""

from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactResult, FactState
from etchlib.versions.parser import extract_version

from .cli import locate, run
from .inventory import marketplaces, plugins
from .schema import target


class CodexFact:
    def __init__(self, kind: str) -> None:
        if kind not in ("command", "version", "marketplaces", "plugins"):
            raise ValueError("unsupported Codex fact")
        self.kind, self.name = kind, "codex." + kind

    def validate(self, config: Any, context: Context) -> None:
        target(config)

    def gather(self, config: Any, context: Context) -> FactResult:
        options = target(config)
        executable = locate(options, context)
        if executable is None:
            return FactResult(
                FactState.UNAVAILABLE,
                reason="Codex command {!r} not found or not executable".format(
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
        if self.kind == "marketplaces":
            return FactResult(
                FactState.VALUE, marketplaces(executable, options, context)
            )
        return FactResult(FactState.VALUE, list(plugins(executable, options, context)))
