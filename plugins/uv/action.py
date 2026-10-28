"""Install only missing user tools into pinned native uv directories."""

from dataclasses import dataclass, replace
from typing import Any, Optional

from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import Directories, capture, directories, environment_key, installed, locate
from .schema import Target, action_options


@dataclass(frozen=True)
class Tools:
    target: Target
    executable: str
    paths: Optional[Directories]
    environment: str
    desired: tuple[str, ...]
    missing: tuple[str, ...]


class UvAction:
    name = "uv"

    def validate(self, config: Any, context: Context) -> None:
        action_options(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        target, desired = action_options(config, context)
        executable = locate(target, context)
        if executable is None:
            raise ValueError(
                "uv command {!r} is unavailable; install uv and expose its CLI first".format(
                    target.command
                )
            )
        paths = directories(executable, target, context) if desired else None
        current = (
            set(installed(executable, target, paths, context))
            if paths is not None
            else set()
        )
        missing = tuple(name for name in desired if name not in current)
        return Inspection(
            InspectionState.CHANGE if missing else InspectionState.SATISFIED,
            Tools(target, executable, paths, environment_key(), desired, missing),
            "{} requested uv tools missing".format(len(missing)),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Tools = observation.data
        description = (
            "Install uv tools: "
            + ", ".join(state.missing)
            + "; package builds may execute code"
            if state.missing
            else "uv tools already installed"
        )
        description += " [executable: {}".format(state.executable)
        if state.paths is not None:
            description += "; tools: {}; executables: {}".format(
                state.paths.tools, state.paths.executables
            )
        return Plan(
            PlanStatus.CHANGE if state.missing else PlanStatus.SKIP,
            description + "]",
            payload=state,
            resources=("package-manager:uv",),
            network=bool(state.missing),
            opaque=bool(state.missing),
            reusable=True,
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        state: Tools = plan.payload
        context = replace(context, inspection_cache=None)
        if locate(state.target, context) != state.executable:
            raise ValueError("uv executable changed since planning")
        if not state.desired:
            return ApplyResult(False, "No uv tools requested")
        if environment_key() != state.environment:
            raise ValueError(
                "uv environment changed since planning; plan again for the intended environment"
            )
        paths = directories(state.executable, state.target, context)
        if paths != state.paths:
            raise ValueError(
                "uv tool directories changed since planning; plan again for the intended target"
            )
        current = set(installed(state.executable, state.target, paths, context))
        changed = []
        for name in state.desired:
            if name in current:
                continue
            # A requirement specifier prevents uv from interpreting a name as a local path.
            capture(
                state.executable,
                state.target,
                ("tool", "install", "--no-python-downloads", "--", name + ">=0"),
                context,
                paths,
            )
            current = set(installed(state.executable, state.target, paths, context))
            if name not in current:
                raise ValueError(
                    "uv reported success but tool remains missing: " + name
                )
            changed.append(name)
        if set(state.desired) - current:
            raise ValueError("uv requested tools remain missing after installation")
        return ApplyResult(
            bool(changed),
            "Installed uv tools: " + ", ".join(changed)
            if changed
            else "uv tools already installed",
        )
