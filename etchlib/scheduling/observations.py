"""Prevent inspection of work whose predecessors or observations are changing."""

from typing import Any, Collection

from etchlib.config import Repository
from etchlib.graph.model import NodeId
from etchlib.planning.model import Report
from etchlib.providers.observations import FactRef

from .resources import requirements


def condition_facts(value: Any, module: str) -> set[FactRef]:
    refs: set[FactRef] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "fact":
                for fact in child if isinstance(child, list) else [child]:
                    refs.add(FactRef(module, fact["name"]))
            elif key in ("os", "arch", "distro"):
                refs.add(FactRef(None, key))
            else:
                refs.update(condition_facts(child, module))
    return refs


def refreshed(
    repository: Repository, report: Report, key: NodeId
) -> tuple[FactRef, ...]:
    module = next(module for module in repository.modules if module.name == key.module)
    return tuple(
        dict.fromkeys(
            [
                FactRef(module.name, name)
                for name in module.config["actions"][key.index].get("refresh", [])
            ]
            + list(report.plans[key].refresh)
        )
    )


def frozen_actions(
    repository: Repository,
    report: Report,
    running: Collection[NodeId],
    completed: Collection[NodeId],
) -> set[NodeId]:
    frozen = set(running)
    writes = {ref for key in running for ref in refreshed(repository, report, key)}
    resources = {name for key in running for name in requirements(report.plans[key])}
    nodes = set(report.graph.order())
    for module in repository.modules:
        for index, action in enumerate(module.config.get("actions", [])):
            key = NodeId(module.name, "action", index)
            if key in completed or key in running:
                continue
            plan = report.plans.get(key)
            reads = condition_facts(
                module.config.get("when"), module.name
            ) | condition_facts(action.get("when"), module.name)
            if plan is not None:
                reads.update(plan.facts)
            ancestors = report.graph.ancestors(key) if key in nodes else set()
            if (
                any(
                    parent.kind == "action" and parent not in completed
                    for parent in ancestors
                )
                or reads & writes
                or (plan is None and bool(writes))
                or (resources and (plan is None or requirements(plan) & resources))
            ):
                frozen.add(key)
    return frozen


def reads(repository: Repository, report: Report, key: NodeId) -> set[FactRef]:
    module = next(module for module in repository.modules if module.name == key.module)
    action = module.config["actions"][key.index]
    return (
        condition_facts(module.config.get("when"), module.name)
        | condition_facts(action.get("when"), module.name)
        | set(report.plans[key].facts)
    )


def compatible(
    repository: Repository, report: Report, key: NodeId, running: Collection[NodeId]
) -> bool:
    incoming_reads = reads(repository, report, key)
    incoming_writes = set(refreshed(repository, report, key))
    for other in running:
        other_writes = set(refreshed(repository, report, other))
        if incoming_reads & other_writes or incoming_writes & (
            reads(repository, report, other) | other_writes
        ):
            return False
    return True
