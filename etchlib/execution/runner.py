"""Fail-fast serial execution, with fresh validation between successful actions."""

from types import MappingProxyType
from typing import Optional

from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.facts.repository import repository_facts
from etchlib.graph.model import NodeId
from etchlib.planning.build import plan_repository
from etchlib.planning.context import provider_context
from etchlib.planning.model import Report
from etchlib.providers.lifecycle import apply_action
from etchlib.providers.observations import FactRef
from etchlib.providers.plans import PlanStatus
from etchlib.providers.registry import Registry
from etchlib.scheduling.resources import options

from .results import ActionResult, ExecutionReport, Status
from .validation import validate_progress, validate_refresh


def apply_repository(
    repository: Repository,
    registry: Registry,
    *,
    allow_sudo: bool = False,
    jobs: Optional[int] = None,
) -> ExecutionReport:
    settings = options(repository.defaults.get("execution", {}), jobs)
    if settings.jobs > 1:
        from etchlib.scheduling.engine import Scheduler

        return Scheduler(repository, registry, settings, allow_sudo).run()
    store = repository_facts(repository, registry)
    modules = {module.name: module for module in repository.modules}
    results: dict[NodeId, ActionResult] = {}
    report: Optional[Report] = None
    error = None
    warnings: dict[str, None] = {}
    current: Optional[NodeId] = None
    try:
        validate_refresh(repository, store)
        while True:
            current = None
            report = plan_repository(
                repository,
                registry,
                store=store,
                previous=report,
                completed=tuple(results),
            )
            validate_progress(report, tuple(results), allow_sudo)
            warnings.update(dict.fromkeys(report.graph.warnings))
            pending = [
                key
                for key in report.graph.order()
                if key.kind == "action" and key not in results
            ]
            if not pending:
                break
            current = pending[0]
            if report.graph.node(current).outcome is not Outcome.TRUE:
                raise ValueError(
                    "{}: blocked by an unresolved condition".format(current)
                )
            plan = report.plans[current]
            if plan.status is PlanStatus.SKIP:
                results[current] = ActionResult(
                    current, Status.SKIPPED, plan.description
                )
                continue
            module = modules[current.module]
            context = provider_context(repository, module, store, allow_sudo)
            outcome = apply_action(report.providers[current], plan, context)
            refresh = tuple(
                dict.fromkeys(
                    [
                        FactRef(module.name, name)
                        for name in module.config["actions"][current.index].get(
                            "refresh", []
                        )
                    ]
                    + list(plan.refresh)
                )
            )
            # A successful provider return is the only invalidation boundary.
            # Even a no-change return may follow an external change since inspection.
            for ref in refresh:
                store.invalidate(ref)
            results[current] = ActionResult(
                current,
                Status.CHANGED if outcome.changed else Status.UNCHANGED,
                outcome.description,
                refresh,
            )
    except (ValueError, OSError) as exc:
        error = str(exc)
        if current is not None:
            results[current] = ActionResult(current, Status.FAILED, error)
    except KeyboardInterrupt:
        error = (
            "Interrupted; an in-progress action may have partially changed the system"
        )
        if current is not None:
            results[current] = ActionResult(current, Status.FAILED, error)
    for module in repository.modules:
        for index, _ in enumerate(module.config.get("actions", [])):
            key = NodeId(module.name, "action", index)
            if key not in results:
                results[key] = ActionResult(
                    key,
                    Status.BLOCKED if error else Status.SKIPPED,
                    "Not run after failure (fail-fast policy)"
                    if error
                    else "Condition false",
                )
    return ExecutionReport(
        tuple(results.values()),
        MappingProxyType({ref: store.peek(ref) for ref in store.references()}),
        tuple(warnings),
        error,
    )
