"""Run planned lifecycle work only after successful serial or parallel execution."""

from dataclasses import replace
from typing import Optional

from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.graph.model import NodeId
from etchlib.housekeeping.planning import claimed
from etchlib.housekeeping.scope import configuration, removed_module
from etchlib.planning.model import Report

from .results import ActionResult, ExecutionReport, Status


def finish(
    repository: Repository, result: ExecutionReport, report: Optional[Report]
) -> ExecutionReport:
    if report is None or report.maintenance is None or not report.maintenance.tasks:
        return result
    if not result.succeeded:
        return replace(
            result,
            warnings=result.warnings
            + ("Automatic cleanup deferred because apply did not succeed.",),
        )
    actions = list(result.actions)
    try:
        if configuration(repository.root) != report.maintenance.configuration:
            raise ValueError(
                "configuration changed during apply; automatic cleanup deferred"
            )
        removed_owners: dict[str, bool] = {}
        for index, task in enumerate(report.maintenance.tasks):
            if task.removed_owner:
                if task.module not in removed_owners:
                    removed_owners[task.module] = removed_module(
                        repository.root, task.module
                    )
                if not removed_owners[task.module]:
                    continue
            if task.operation == "retire" and not task.removed_owner:
                selection = report.selections.get(task.module)
                if (
                    selection is None
                    or selection.module.outcome is not Outcome.TRUE
                    or any(
                        result.outcome is Outcome.DEFERRED
                        for result in selection.actions
                    )
                ):
                    continue
            if (
                task.operation == "retire"
                and task.target is not None
                and claimed(task.target, report.plans, repository.root)
            ):
                continue
            changed = task.apply(repository.root)
            if changed:
                actions.append(
                    ActionResult(
                        NodeId(task.module, "housekeeping", index),
                        Status.CHANGED,
                        task.description,
                    )
                )
    except (ValueError, OSError) as exc:
        return replace(
            result,
            actions=tuple(actions),
            error="Automatic cleanup failed: {}".format(exc),
        )
    return replace(result, actions=tuple(actions))
