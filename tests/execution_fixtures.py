"""Stateful providers for execution and refresh assertions."""

from typing import Any

from etchlib.config import load_repository
from etchlib.execution.results import ExecutionReport
from etchlib.execution.runner import apply_repository
from etchlib.providers.contracts import Context
from etchlib.providers.observations import (
    FactRef,
    FactResult,
    FactState,
    Inspection,
    InspectionState,
)
from etchlib.providers.plans import ApplyResult, PathClaim, Plan, PlanStatus
from etchlib.providers.registry import Origin
from tests.planning_fixtures import PlanningFixture


class StateFact:
    name = "state"

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.calls: list[str] = []

    def validate(self, config: Any, context: Context) -> None:
        pass

    def gather(self, config: Any, context: Context) -> FactResult:
        self.calls.append(config)
        if config not in self.values:
            return FactResult(FactState.UNAVAILABLE, reason="not established")
        return FactResult(FactState.VALUE, self.values[config])


class Establish:
    name = "establish"

    def __init__(self, fact: StateFact) -> None:
        self.fact = fact
        self.calls: list[str] = []
        self.applied: list[str] = []

    def validate(self, config: Any, context: Context) -> None:
        if config.get("invalid"):
            raise ValueError("bad activated configuration")

    def inspect(self, config: Any, context: Context) -> Inspection:
        self.calls.append(config["name"])
        return Inspection(InspectionState.CHANGE)

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        return Plan(
            PlanStatus.SKIP if config.get("skip") else PlanStatus.CHANGE,
            "Establish " + config["name"],
            payload=config,
            refresh=tuple(FactRef(*ref) for ref in config.get("refreshes", [])),
            requires=tuple(config.get("requires", [])),
            claims=(PathClaim(context.repo_root / config["claim"]),)
            if "claim" in config
            else (),
            elevated=config.get("sudo", False),
            resources=tuple(config.get("resources", [])),
            facts=tuple(FactRef(*ref) for ref in config.get("facts", [])),
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        config = plan.payload
        self.applied.append(config["name"])
        if config.get("fail"):
            raise ValueError("producer failed")
        self.fact.values.update(config.get("values", {}))
        return ApplyResult(config.get("changed", True), "Established " + config["name"])


class ExecutionFixture(PlanningFixture):
    def setUp(self) -> None:
        super().setUp()
        self.fact = StateFact()
        self.action = Establish(self.fact)
        self.registry.register(
            Origin("test", "1"), actions=[self.action], facts=[self.fact]
        )

    def apply_repo(self, allow_sudo: bool = False) -> ExecutionReport:
        return apply_repository(
            load_repository(self.root), self.registry, allow_sudo=allow_sudo
        )

    def staged(self, **producer: Any) -> None:
        self.module(
            facts={"tool": {"state": "tool"}},
            actions=[
                {
                    "establish": dict(
                        name="install", values={"tool": "1.2.3"}, **producer
                    ),
                    "refresh": ["tool"],
                },
                {
                    "establish": {"name": "configure"},
                    "when": {"fact": {"name": "tool", "matches": ">=1"}},
                },
            ],
        )
