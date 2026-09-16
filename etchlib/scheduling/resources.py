"""Named resource capacities; no provider-specific dispatch."""

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional

from etchlib.providers.plans import Plan

INTERACTIVE = {"terminal", "sudo-interactive", "stdin-interactive"}


def resource_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and re.fullmatch(r"[a-z][a-z0-9_.-]*(?::[a-z0-9][a-z0-9_.-]*)?", name)
        is not None
    )


@dataclass(frozen=True)
class Options:
    jobs: int
    capacities: Mapping[str, int]


def options(value: Any, jobs: Optional[int] = None) -> Options:
    if not isinstance(value, dict) or set(value) - {"jobs", "resources"}:
        raise ValueError("execution accepts jobs and resources")
    count = value.get("jobs", 1) if jobs is None else jobs
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError("execution jobs must be an integer from 1 to 64")
    capacities = value.get("resources", {})
    if not isinstance(capacities, dict):
        raise ValueError("execution resources must map names to capacities")
    for name, capacity in capacities.items():
        if not resource_name(name) or type(capacity) is not int or capacity < 1:
            raise ValueError(
                "resource capacities require valid names and positive integers"
            )
        if name in INTERACTIVE and capacity != 1:
            raise ValueError("interactive resource capacities must remain one")
    return Options(count, MappingProxyType(dict(capacities)))


def requirements(plan: Plan) -> frozenset[str]:
    names = set(plan.resources)
    if any(not resource_name(name) for name in names):
        raise ValueError("plan contains an invalid resource name")
    if plan.elevated:
        names.add("sudo-interactive")
    if names & INTERACTIVE:
        names.add("terminal")
    return frozenset(names)


class Resources:
    def __init__(self, capacities: Mapping[str, int]) -> None:
        self.capacities = capacities
        self.used: dict[str, int] = {}

    def available(self, names: frozenset[str]) -> bool:
        return all(
            self.used.get(name, 0) < self.capacities.get(name, 1) for name in names
        )

    def acquire(self, names: frozenset[str]) -> None:
        if not self.available(names):
            raise ValueError("resources are not available")
        for name in names:
            self.used[name] = self.used.get(name, 0) + 1

    def release(self, names: frozenset[str]) -> None:
        for name in names:
            self.used[name] -= 1
