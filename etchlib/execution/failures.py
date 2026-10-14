"""Conservative module failure isolation shared by serial and parallel apply."""

from dataclasses import replace
from typing import Mapping, Optional

from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.facts.store import FactStore
from etchlib.graph.model import NodeId
from etchlib.planning.model import Report

from .results import ActionResult, Status


def blocked_actions(
    repository: Repository, report: Report, results: Mapping[NodeId, ActionResult]
) -> dict[NodeId, NodeId]:
    causes = {
        key.module: key
        for key, result in results.items()
        if result.status is Status.FAILED
    }
    if not causes:
        return {}
    # Include declarations for deferred gates whose dependency edges are not active yet.
    changed = True
    while changed:
        changed = False
        for module in repository.modules:
            if (
                module.name in causes
                or report.selections[module.name].module.outcome is Outcome.FALSE
            ):
                continue
            targets = list(module.config.get("requires", [])) + list(
                module.config.get("after", [])
            )
            for index, action in enumerate(module.config.get("actions", [])):
                targets.extend(action.get("requires", []))
                targets.extend(action.get("after", []))
                plan = report.plans.get(NodeId(module.name, "action", index))
                if plan is not None:
                    targets.extend(plan.requires)
                    targets.extend(plan.after)
            cause = next(
                (causes[target] for target in targets if target in causes), None
            )
            if cause is not None:
                causes[module.name] = cause
                changed = True
    return {
        NodeId(module.name, "action", index): causes[module.name]
        for module in repository.modules
        if module.name in causes
        for index, _ in enumerate(module.config.get("actions", []))
        if NodeId(module.name, "action", index) not in results
    }


def failed_snapshot(store: FactStore, report: Report) -> Report:
    # Failed providers may have partially changed state outside declared refreshes.
    for ref in store.references():
        store.invalidate(ref)
    return replace(
        report,
        plans={
            key: replace(plan, reusable=False) for key, plan in report.plans.items()
        },
    )


def failure_summary(results: Mapping[NodeId, ActionResult]) -> Optional[str]:
    errors = [
        "{}: {}".format(key, result.description)
        for key, result in results.items()
        if result.status is Status.FAILED
    ]
    return "\n".join(errors) or None


def blocked_result(key: NodeId, cause: NodeId) -> ActionResult:
    return ActionResult(
        key, Status.BLOCKED, "Not run: blocked by failure in {}".format(cause)
    )
