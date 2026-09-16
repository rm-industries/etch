"""Bounded DAG dispatch with atomic reservations and coordinator-owned refresh."""

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from types import MappingProxyType
from typing import Optional

from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.execution.results import ActionResult, ExecutionReport, Status
from etchlib.execution.validation import validate_progress, validate_refresh
from etchlib.facts.repository import repository_facts
from etchlib.graph.model import NodeId
from etchlib.planning.build import plan_repository
from etchlib.planning.model import Report
from etchlib.providers.plans import PlanStatus
from etchlib.providers.registry import Registry

from .observations import compatible, frozen_actions, refreshed
from .resources import Options, Resources, requirements
from .tasks import context_snapshot, invoke, validate_started


class Scheduler:
    def __init__(
        self,
        repository: Repository,
        registry: Registry,
        settings: Options,
        allow_sudo: bool,
    ) -> None:
        self.repository, self.registry = repository, registry
        self.settings, self.allow_sudo = settings, allow_sudo
        self.store = repository_facts(repository, registry)
        self.resources = Resources(settings.capacities)
        self.results: dict[NodeId, ActionResult] = {}
        self.started: dict[NodeId, set[NodeId]] = {}
        self.running: dict[NodeId, Future[ActionResult]] = {}
        self.report: Optional[Report] = None
        self.error: Optional[str] = None
        self.warnings: dict[str, None] = {}

    def snapshot(self) -> set[NodeId]:
        frozen = (
            frozen_actions(self.repository, self.report, self.running, self.results)
            if self.report
            else set()
        )
        self.report = plan_repository(
            self.repository,
            self.registry,
            store=self.store,
            previous=self.report,
            completed=tuple(self.results),
            frozen=frozen,
        )
        validate_progress(self.report, tuple(self.results), self.allow_sudo)
        validate_started(self.report, self.started)
        self.warnings.update(dict.fromkeys(self.report.graph.warnings))
        return frozen

    def dispatch(self, pool: ThreadPoolExecutor, frozen: set[NodeId]) -> bool:
        assert self.report is not None
        dispatched = False
        for key in self.report.graph.order():
            if len(self.running) >= self.settings.jobs:
                break
            if key.kind != "action" or key in self.started or key in frozen:
                continue
            if self.report.graph.node(key).outcome is not Outcome.TRUE:
                continue
            if any(
                parent.kind == "action" and parent not in self.results
                for parent in self.report.graph.ancestors(key)
            ):
                continue
            plan = self.report.plans[key]
            names = requirements(plan)
            if not self.resources.available(names) or not compatible(
                self.repository, self.report, key, self.running
            ):
                continue
            self.started[key] = set(self.results)
            dispatched = True
            if plan.status is PlanStatus.SKIP:
                self.results[key] = ActionResult(key, Status.SKIPPED, plan.description)
                continue
            context = context_snapshot(
                self.repository, key, self.store, self.allow_sudo
            )
            self.resources.acquire(names)
            self.running[key] = pool.submit(
                invoke,
                key,
                self.report.providers[key],
                plan,
                context,
                refreshed(self.repository, self.report, key),
            )
        return dispatched

    def collect(self) -> None:
        assert self.report is not None
        wait(tuple(self.running.values()), return_when=FIRST_COMPLETED)
        # Process the available batch in dispatch order, never unordered set order.
        for key, future in tuple(self.running.items()):
            if not future.done():
                continue
            result = future.result()
            self.results[key] = result
            self.resources.release(requirements(self.report.plans[key]))
            del self.running[key]
            if result.status is Status.FAILED:
                self.error = self.error or result.description
            else:
                for ref in result.refreshed:
                    self.store.invalidate(ref)

    def run(self) -> ExecutionReport:
        with ThreadPoolExecutor(
            max_workers=self.settings.jobs, thread_name_prefix="etch"
        ) as pool:
            try:
                validate_refresh(self.repository, self.store)
                while self.error is None:
                    frozen = self.snapshot()
                    dispatched = self.dispatch(pool, frozen)
                    if self.running:
                        self.collect()
                    elif not dispatched:
                        assert self.report is not None
                        pending = [
                            key
                            for key in self.report.graph.order()
                            if key.kind == "action" and key not in self.results
                        ]
                        if pending and frozen != frozen_actions(
                            self.repository, self.report, self.running, self.results
                        ):
                            # A gate resolved false and removed a predecessor.
                            # Reinspect newly unblocked work before dispatch.
                            continue
                        if pending:
                            raise ValueError(
                                "Blocked work has no ready producer: "
                                + ", ".join(map(str, pending))
                            )
                        break
            except (ValueError, OSError) as exc:
                self.error = str(exc)
            except KeyboardInterrupt:
                self.error = "Interrupted; waiting for in-flight actions to finish"
            # Running mutations cannot be safely canceled or rolled back. No new
            # actions are admitted after failure, but every running result is kept.
            while self.running:
                self.collect()
        ordered = {
            key: self.results[key] for key in self.started if key in self.results
        }
        for module in self.repository.modules:
            for index, _ in enumerate(module.config.get("actions", [])):
                key = NodeId(module.name, "action", index)
                if key not in ordered:
                    ordered[key] = ActionResult(
                        key,
                        Status.BLOCKED if self.error else Status.SKIPPED,
                        "Not run after failure (fail-fast policy)"
                        if self.error
                        else "Condition false",
                    )
        return ExecutionReport(
            tuple(ordered.values()),
            MappingProxyType(
                {ref: self.store.peek(ref) for ref in self.store.references()}
            ),
            tuple(self.warnings),
            self.error,
        )
