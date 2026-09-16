"""Validate declared refreshes, privilege requests, and execution history."""

from typing import Collection

from etchlib.config import Repository
from etchlib.facts.store import FactStore
from etchlib.graph.model import GraphError, NodeId
from etchlib.planning.model import Report
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import FactRef
from etchlib.scheduling.resources import requirements


def validate_refresh(repository: Repository, store: FactStore) -> None:
    declared = set(store.references())
    for module in repository.modules:
        for index, action in enumerate(module.config.get("actions", [])):
            for name in action.get("refresh", []):
                if FactRef(module.name, name) not in declared:
                    raise GraphError(
                        "{}: undeclared refresh fact {!r}".format(
                            NodeId(module.name, "action", index), name
                        )
                    )


def validate_progress(
    report: Report, completed: Collection[NodeId], allow_sudo: bool
) -> None:
    preceding: set[NodeId] = set()
    for key in completed:
        unfinished = {
            parent
            for parent in report.graph.ancestors(key)
            if parent.kind == "action" and parent not in preceding
        }
        if unfinished:
            raise GraphError(
                "{}: activated dependencies would precede an already completed action: {}".format(
                    key, ", ".join(str(node) for node in sorted(unfinished, key=str))
                )
            )
        preceding.add(key)
    for key, plan in report.plans.items():
        requirements(plan)
        if key not in completed and plan.elevated and not allow_sudo:
            raise ProviderError(
                "{}: privilege escalation requires --allow-sudo".format(key)
            )
