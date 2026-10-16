"""Serial execution continues independent modules after isolated action failures."""

from collections import deque
from types import MappingProxyType
from typing import Callable, Optional

from etchlib.conditions.render import describe_condition
from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.diagnostics.timing import TimingSink
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

from .failures import blocked_actions, blocked_result, failed_snapshot, failure_summary
from .housekeeping import finish
from .results import ActionResult, ExecutionReport, Status
from .validation import validate_progress, validate_refresh


def apply_repository(
    repository: Repository,
    registry: Registry,
    *,
    allow_sudo: bool = False,
    jobs: Optional[int] = None,
    on_start: Optional[Callable[[str], None]] = None,
    on_inspect: Optional[Callable[[str], None]] = None,
    verbose: bool = False,
    timings: Optional[TimingSink] = None,
) -> ExecutionReport:
    settings = options(repository.defaults.get("execution", {}), jobs)
    if settings.jobs > 1:
        from etchlib.scheduling.engine import Scheduler

        scheduler = Scheduler(
            repository,
            registry,
            settings,
            allow_sudo,
            on_start,
            on_inspect,
            verbose,
            timings,
        )
        return finish(repository, scheduler.run(), scheduler.report)
    store = repository_facts(repository, registry, timings)
    modules = {module.name: module for module in repository.modules}
    results: dict[NodeId, ActionResult] = {}
    report: Optional[Report] = None
    error = None
    warnings: dict[str, None] = {}
    current: Optional[NodeId] = None
    announced: set[str] = set()
    needs_snapshot = True
    pending: deque[NodeId] = deque()
    blocked: dict[NodeId, NodeId] = {}
    try:
        validate_refresh(repository, store)
        while True:
            current = None
            if needs_snapshot:
                report = plan_repository(
                    repository,
                    registry,
                    store=store,
                    previous=report,
                    completed=tuple(results),
                    frozen=tuple(blocked),
                    on_inspect=on_inspect,
                )
                validate_progress(report, tuple(results), allow_sudo)
                blocked.update(blocked_actions(repository, report, results))
                warnings.update(dict.fromkeys(report.graph.warnings))
                pending = deque(
                    key
                    for key in report.graph.order()
                    if key.kind == "action"
                    and key not in results
                    and key not in blocked
                )
                needs_snapshot = False
            assert report is not None
            if not pending:
                break
            current = pending.popleft()
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
            if on_start is not None and current.module not in announced:
                on_start(current.module)
                announced.add(current.module)
            module = modules[current.module]
            context = provider_context(repository, module, store, allow_sudo, verbose)
            try:
                outcome = apply_action(report.providers[current], plan, context)
            except (ValueError, OSError) as exc:
                results[current] = ActionResult(current, Status.FAILED, str(exc))
                blocked.update(blocked_actions(repository, report, results))
                report = failed_snapshot(store, report)
                needs_snapshot = True
                continue
            # Executed providers may change external state even without fact refresh.
            needs_snapshot = True
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
            if key in blocked and key not in results:
                results[key] = blocked_result(key, blocked[key])
            if key not in results:
                results[key] = ActionResult(
                    key,
                    Status.BLOCKED if error else Status.SKIPPED,
                    "Not run: apply stopped after a safety error or interruption"
                    if error
                    else "Not run: "
                    + describe_condition(
                        (
                            module.config.get("when", {})
                            if report is not None
                            and report.selections[module.name].module.outcome
                            is Outcome.FALSE
                            else module.config["actions"][index].get("when", {})
                        ),
                    ),
                )
    result = ExecutionReport(
        tuple(results.values()),
        MappingProxyType({ref: store.peek(ref) for ref in store.references()}),
        tuple(warnings),
        error or failure_summary(results),
    )

    return finish(repository, result, report)
