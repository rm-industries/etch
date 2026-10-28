"""Presence-only user plugin reconciliation through the native Claude CLI."""

from dataclasses import dataclass, replace
from typing import Any

from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .cli import locate, run
from .inventory import marketplaces, plugins
from .schema import Target, action_options


@dataclass(frozen=True)
class Reconciliation:
    target: Target
    executable: str
    marketplaces: tuple[str, ...]
    plugins: tuple[str, ...]
    missing: tuple[str, ...]


class ClaudeAction:
    name = "claude"

    def validate(self, config: Any, context: Context) -> None:
        action_options(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        target, desired_markets, desired_plugins = action_options(config, context)
        executable = locate(target, context)
        if executable is None:
            raise ValueError(
                "Claude command {!r} is unavailable; install a CLI supporting plugin commands first".format(
                    target.command
                )
            )
        markets = marketplaces(executable, target, context) if desired_markets else {}
        current = (
            set(plugins(executable, target, context)) if desired_plugins else set()
        )
        missing = tuple(
            "marketplace " + item
            for item in desired_markets
            if item not in markets.values()
        ) + tuple("plugin " + item for item in desired_plugins if item not in current)
        return Inspection(
            InspectionState.CHANGE if missing else InspectionState.SATISFIED,
            Reconciliation(
                target, executable, desired_markets, desired_plugins, missing
            ),
            "{} requested entries missing".format(len(missing)),
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        state: Reconciliation = observation.data
        return Plan(
            PlanStatus.CHANGE if state.missing else PlanStatus.SKIP,
            "Install Claude entries (native plugin installation may execute code):\n"
            + "\n".join("- " + item for item in state.missing)
            if state.missing
            else "Claude marketplaces and plugins already installed",
            payload=state,
            resources=("application:claude",),
            network=bool(state.missing),
            opaque=bool(state.missing),
            reusable=True,
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        state: Reconciliation = plan.payload
        context = replace(context, inspection_cache=None)
        if locate(state.target, context) != state.executable:
            raise ValueError("Claude executable changed since planning")
        markets = (
            marketplaces(state.executable, state.target, context)
            if state.marketplaces
            else {}
        )
        changed = []
        for item in state.marketplaces:
            if item not in markets.values():
                run(
                    state.executable,
                    state.target,
                    ("plugin", "marketplace", "add", item, "--scope", "user"),
                    context,
                )
                markets = marketplaces(state.executable, state.target, context)
                if item not in markets.values():
                    raise ValueError(
                        "Claude reported success but marketplace remains missing: "
                        + item
                    )
                changed.append("marketplace " + item)
        current = (
            set(plugins(state.executable, state.target, context))
            if state.plugins
            else set()
        )
        for item in state.plugins:
            if item not in current:
                run(
                    state.executable,
                    state.target,
                    ("plugin", "install", item, "--scope", "user"),
                    context,
                )
                current = set(plugins(state.executable, state.target, context))
                if item not in current:
                    raise ValueError(
                        "Claude reported success but plugin remains missing: " + item
                    )
                changed.append("plugin " + item)
        if set(state.plugins) - current:
            raise ValueError(
                "Claude requested plugins remain missing after installation"
            )
        return ApplyResult(
            bool(changed),
            "Installed Claude entries:\n" + "\n".join("- " + item for item in changed)
            if changed
            else "Claude marketplaces and plugins already installed",
        )
