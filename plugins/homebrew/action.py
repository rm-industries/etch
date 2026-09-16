"""Batch missing formulae and casks without requesting upgrades or removals."""

from dataclasses import dataclass
from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import installed, locate, run
from .schema import Target, action_options


@dataclass(frozen=True)
class Packages:
    target: Target
    executable: str
    formulae: tuple[str, ...]
    casks: tuple[str, ...]
    missing_formulae: tuple[str, ...]
    missing_casks: tuple[str, ...]


class BrewAction:
    name = "brew"

    def validate(self, config: Any, context: Context) -> None:
        action_options(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        target, formulae, casks = action_options(config, context)
        executable = locate(target, context)
        if executable is None:
            raise ValueError(
                "Homebrew command {!r} is unavailable; install Homebrew and expose its CLI first".format(
                    target.command
                )
            )
        current_formulae = (
            installed(executable, target, "formula", context) if formulae else ()
        )
        current_casks = installed(executable, target, "cask", context) if casks else ()
        missing_formulae = tuple(
            name for name in formulae if name not in current_formulae
        )
        missing_casks = tuple(name for name in casks if name not in current_casks)
        return Inspection(
            InspectionState.CHANGE
            if missing_formulae or missing_casks
            else InspectionState.SATISFIED,
            Packages(
                target, executable, formulae, casks, missing_formulae, missing_casks
            ),
            "{} requested formulae and {} requested casks missing".format(
                len(missing_formulae), len(missing_casks)
            ),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Packages = observation.data
        changes = []
        for kind, names in (
            ("formulae", state.missing_formulae),
            ("casks", state.missing_casks),
        ):
            if names:
                changes.append(kind + ": " + ", ".join(names))
        return Plan(
            PlanStatus.CHANGE if changes else PlanStatus.SKIP,
            (
                "Install Homebrew " + "; ".join(changes)
                if changes
                else "Homebrew packages already installed"
            )
            + " [executable: {}]".format(state.executable),
            payload=state,
            resources=("package-manager:brew",),
            network=bool(changes),
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        state: Packages = plan.payload
        executable = locate(state.target, context)
        if executable != state.executable:
            raise ValueError("Homebrew executable changed since planning")
        changes = []
        for kind, desired in (("formula", state.formulae), ("cask", state.casks)):
            if not desired:
                continue
            current = installed(executable, state.target, kind, context)
            missing = tuple(name for name in desired if name not in current)
            if not missing:
                continue
            run(executable, state.target, ("install", "--" + kind, *missing), context)
            remaining = set(desired) - set(
                installed(executable, state.target, kind, context)
            )
            if remaining:
                raise ValueError(
                    "Homebrew reported success but packages remain missing: "
                    + ", ".join(sorted(remaining))
                )
            changes.append(kind + ": " + ", ".join(missing))
        return ApplyResult(
            bool(changes),
            "Installed Homebrew " + "; ".join(changes)
            if changes
            else "Homebrew packages already installed",
        )
