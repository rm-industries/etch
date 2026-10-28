"""Install only missing global registry packages, preserving existing versions."""

from dataclasses import dataclass, replace
from typing import Any, Optional

from etchlib.providers import native
from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import environment_key, global_prefix, installed, locate, run
from .schema import Target, action_options


@dataclass(frozen=True)
class Packages:
    target: Target
    executable: str
    prefix: Optional[str]
    environment: str
    desired: tuple[str, ...]
    missing: tuple[str, ...]


class NpmAction:
    name = "npm"

    def validate(self, config: Any, context: Context) -> None:
        action_options(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        target, desired = action_options(config, context)
        executable = locate(target, context)
        prefix = global_prefix(executable, target, context) if desired else None
        current = (
            set(installed(executable, target, prefix, context))
            if prefix is not None
            else set()
        )
        missing = tuple(name for name in desired if name not in current)
        return Inspection(
            InspectionState.CHANGE if missing else InspectionState.SATISFIED,
            Packages(target, executable, prefix, environment_key(), desired, missing),
            "{} requested global npm packages missing".format(len(missing)),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Packages = observation.data
        return Plan(
            PlanStatus.CHANGE if state.missing else PlanStatus.SKIP,
            (
                "Install global npm packages: "
                + ", ".join(state.missing)
                + "; npm lifecycle scripts may execute under the configured npm policy"
                if state.missing
                else "Global npm packages already installed"
            )
            + " [executable: {}; prefix: {}]".format(
                state.executable, state.prefix or "unused"
            ),
            payload=state,
            resources=("package-manager:npm",),
            network=bool(state.missing),
            opaque=bool(state.missing),
            reusable=True,
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        state: Packages = plan.payload
        context = replace(context, inspection_cache=None)
        if native.locate(state.target.command, context.module_root) != state.executable:
            raise ValueError("npm executable changed since planning")
        if not state.desired:
            return ApplyResult(False, "No global npm packages requested")
        if environment_key() != state.environment:
            raise ValueError(
                "npm environment changed since planning; plan again for the intended environment"
            )
        prefix = global_prefix(state.executable, state.target, context)
        if prefix != state.prefix:
            raise ValueError(
                "npm global prefix changed since planning; plan again for the intended prefix"
            )
        current = set(installed(state.executable, state.target, prefix, context))
        missing = tuple(name for name in state.desired if name not in current)
        if not missing:
            return ApplyResult(False, "Global npm packages already installed")
        # Explicit registry specs prevent npm from treating a name as a local prefix/path.
        run(
            state.executable,
            state.target,
            (
                "install",
                "--global",
                "--prefix=" + prefix,
                "--no-audit",
                "--no-fund",
                "--package-lock=false",
                "--package-lock-only=false",
                "--save=false",
                "--dry-run=false",
                "--",
                *(name + "@*" for name in missing),
            ),
            context,
        )
        remaining = set(state.desired) - set(
            installed(state.executable, state.target, prefix, context)
        )
        if remaining:
            raise ValueError(
                "npm reported success but packages remain missing: "
                + ", ".join(sorted(remaining))
            )
        return ApplyResult(True, "Installed global npm packages: " + ", ".join(missing))
