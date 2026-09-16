"""Worker calls use detached observations; only the coordinator invalidates facts."""

from dataclasses import replace
from types import MappingProxyType

from etchlib.config import Repository
from etchlib.execution.results import ActionResult, Status
from etchlib.facts.store import FactStore
from etchlib.graph.model import NodeId
from etchlib.planning.context import provider_context
from etchlib.planning.model import Report
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import apply_action
from etchlib.providers.observations import FactRef, FactState
from etchlib.providers.plans import Plan
from etchlib.providers.registry import Registration


def context_snapshot(
    repository: Repository, key: NodeId, store: FactStore, allow_sudo: bool
) -> Context:
    module = next(module for module in repository.modules if module.name == key.module)
    facts = {}
    for ref in store.references():
        observation = store.peek(ref)
        if observation is not None and observation.state is not FactState.STALE:
            facts[ref] = observation
    return replace(
        provider_context(repository, module, store, allow_sudo),
        facts=MappingProxyType(facts),
    )


def invoke(
    key: NodeId,
    entry: Registration,
    plan: Plan,
    context: Context,
    refresh: tuple[FactRef, ...],
) -> ActionResult:
    try:
        result = apply_action(entry, plan, context)
        return ActionResult(
            key,
            Status.CHANGED if result.changed else Status.UNCHANGED,
            result.description,
            refresh,
        )
    except (ValueError, OSError) as exc:
        return ActionResult(key, Status.FAILED, str(exc))
    except KeyboardInterrupt:
        return ActionResult(
            key,
            Status.FAILED,
            "Interrupted; action may have partially changed the system",
        )


def validate_started(report: Report, started: dict[NodeId, set[NodeId]]) -> None:
    for key, predecessors in started.items():
        if any(
            parent.kind == "action" and parent not in predecessors
            for parent in report.graph.ancestors(key)
        ):
            raise ValueError(
                "{}: activated dependencies would precede an already started action".format(
                    key
                )
            )
