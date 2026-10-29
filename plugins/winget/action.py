"""Install missing exact WinGet IDs without upgrading installed packages."""

from dataclasses import dataclass, replace
from typing import Any

from etchlib.providers import native
from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import installed, locate, run
from .schema import Target, action_options


@dataclass(frozen=True)
class Packages:
    target: Target
    executable: str
    desired: tuple[str, ...]
    missing: tuple[str, ...]


class WingetAction:
    name = "winget"

    def validate(self, config: Any, context: Context) -> None:
        action_options(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        options, desired = action_options(config, context)
        executable = locate(options, context)
        current = set(installed(executable, options, context)) if desired else set()
        missing = tuple(name for name in desired if name not in current)
        return Inspection(
            InspectionState.CHANGE if missing else InspectionState.SATISFIED,
            Packages(options, executable, desired, missing),
            "{} requested WinGet packages missing".format(len(missing)),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Packages = observation.data
        return Plan(
            PlanStatus.CHANGE if state.missing else PlanStatus.SKIP,
            (
                "Install WinGet packages: "
                + ", ".join(state.missing)
                + "; accepts package/source agreements; installers may request elevation"
                if state.missing
                else "WinGet packages already installed"
            )
            + " [executable: {}; source: {}]".format(
                state.executable, state.target.source
            ),
            payload=state,
            resources=("package-manager:winget",),
            elevated=bool(state.desired),
            network=bool(state.missing),
            opaque=bool(state.missing),
            reusable=True,
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        state: Packages = plan.payload
        context = replace(context, inspection_cache=None)
        if native.locate(state.target.command, context.module_root) != state.executable:
            raise ValueError("winget executable changed since planning")
        if not state.desired:
            return ApplyResult(False, "No WinGet packages requested")
        current = set(installed(state.executable, state.target, context))
        missing = tuple(name for name in state.desired if name not in current)
        if not missing:
            return ApplyResult(False, "WinGet packages already installed")
        added = []
        for name in missing:
            if name in current:
                continue
            run(
                state.executable,
                state.target,
                (
                    "install",
                    "--id",
                    name,
                    "--exact",
                    "--source",
                    state.target.source,
                    "--no-upgrade",
                    "--silent",
                    "--disable-interactivity",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ),
                context,
            )
            added.append(name)
            current = set(installed(state.executable, state.target, context))
            if name not in current:
                raise ValueError(
                    "winget reported success but packages remain missing: " + name
                )
        remaining = set(state.desired) - current
        if remaining:
            raise ValueError(
                "winget reported success but packages remain missing: "
                + ", ".join(sorted(remaining))
            )
        return ApplyResult(True, "Installed WinGet packages: " + ", ".join(added))
