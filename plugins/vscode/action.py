"""Install only missing Marketplace extensions; never remove or upgrade by inference."""

from dataclasses import dataclass
from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import installed, locate, run
from .schema import Target, action_options


@dataclass(frozen=True)
class Reconciliation:
    target: Target
    executable: str
    desired: tuple[str, ...]
    missing: tuple[str, ...]


class VSCodeAction:
    name = "vscode"

    def validate(self, config: Any, context: Context) -> None:
        action_options(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        target, desired = action_options(config, context)
        executable = locate(target, context)
        if executable is None:
            raise ValueError(
                "VS Code command {!r} is unavailable; install VS Code and expose its CLI first".format(
                    target.command
                )
            )
        current = installed(executable, target, context)
        missing = tuple(extension for extension in desired if extension not in current)
        return Inspection(
            InspectionState.CHANGE if missing else InspectionState.SATISFIED,
            Reconciliation(target, executable, desired, missing),
            "{} installed; {} requested extensions missing".format(
                len(current), len(missing)
            ),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Reconciliation = observation.data
        return Plan(
            PlanStatus.CHANGE if state.missing else PlanStatus.SKIP,
            (
                "Install VS Code extensions: " + ", ".join(state.missing)
                if state.missing
                else "VS Code extensions already installed"
            )
            + " [executable: {}]".format(state.executable),
            payload=state,
            resources=("application:vscode",),
            network=bool(state.missing),
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        state: Reconciliation = plan.payload
        executable = locate(state.target, context)
        if executable != state.executable:
            raise ValueError("VS Code executable changed since planning")
        current = set(installed(executable, state.target, context))
        changed = []
        for extension in state.desired:
            if extension not in current:
                run(
                    executable,
                    state.target,
                    ("--install-extension", extension),
                    context,
                )
                changed.append(extension)
                current = set(installed(executable, state.target, context))
                if extension not in current:
                    raise ValueError(
                        "VS Code reported success but extension remains missing: "
                        + extension
                    )
        if changed:
            remaining = set(state.desired) - current
            if remaining:
                raise ValueError(
                    "VS Code reported success but extensions remain missing: "
                    + ", ".join(sorted(remaining))
                )
        return ApplyResult(
            bool(changed),
            "Installed VS Code extensions: " + ", ".join(changed)
            if changed
            else "VS Code extensions already installed",
        )
