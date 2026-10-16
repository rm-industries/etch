"""Inspect active actions, then prove every deferred gate against the graph."""

from copy import deepcopy
from dataclasses import replace
from types import MappingProxyType
from typing import Any, Callable, Collection, Optional, cast

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.conditions.schema import validate
from etchlib.config import Repository
from etchlib.facts.repository import repository_facts
from etchlib.facts.store import FactStore
from etchlib.graph.builder import build_graph
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import NodeId
from etchlib.ownership.claims import validate_claims
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import inspect_action
from etchlib.providers.observations import FactState
from etchlib.providers.plans import PlanStatus
from etchlib.providers.registry import Registry

from .conditions import gate, prove
from .context import provider_context
from .facts import Observations
from .model import Report as Report


def plan_repository(
    repository: Repository,
    registry: Registry,
    *,
    store: Optional[FactStore] = None,
    previous: Optional[Report] = None,
    completed: Collection[NodeId] = (),
    frozen: Collection[NodeId] = (),
    on_inspect: Optional[Callable[[str], None]] = None,
    collect_errors: bool = False,
) -> Report:
    if (completed or frozen) and previous is None:
        raise ValueError("completed actions require their previous snapshot")
    retained = set(completed) | set(frozen)
    retained_modules = {key.module for key in retained}
    frozen_modules = {key.module for key in frozen}
    store = store if store is not None else repository_facts(repository, registry)
    selections, plans, inspections, providers = {}, {}, {}, {}
    errors: dict[NodeId, str] = {}
    issues: list[str] = []
    inspection_cache: dict[tuple[str, ...], Any] = {}

    def checked_gate(config: Any, evaluator: Evaluator, key: NodeId) -> Result:
        try:
            if key in errors:
                return Result(Outcome.DEFERRED, reasons=(errors[key],))
            return gate(config, evaluator)
        except (ValueError, ProviderError, OSError) as exc:
            if not collect_errors:
                raise
            errors[key] = str(exc)
            return Result(Outcome.DEFERRED, reasons=(str(exc),))

    for module in repository.modules:
        if on_inspect is not None:
            on_inspect(module.name)
        actions = module.config.get("actions", [])
        for index, config in enumerate([module.config] + actions):
            if "when" in config:
                try:
                    validate(config["when"])
                except ValueError as exc:
                    if not collect_errors:
                        raise
                    key = (
                        NodeId(module.name, "start")
                        if index == 0
                        else NodeId(module.name, "action", index - 1)
                    )
                    errors[key] = str(exc)
        context = provider_context(
            repository, module, store, inspection_cache=inspection_cache
        )
        evaluator = Evaluator(store, context)
        module_gate = (
            previous.selections[module.name].module
            if previous is not None and module.name in retained_modules
            else checked_gate(module.config, evaluator, NodeId(module.name, "start"))
        )
        results = []
        for index, action in enumerate(actions):
            key = NodeId(module.name, "action", index)
            if key in retained and previous is not None:
                results.append(previous.selections[module.name].actions[index])
                if key in previous.plans:
                    inspections[key] = previous.inspections[key]
                    plans[key] = previous.plans[key]
                    providers[key] = previous.providers[key]
                continue
            result = (
                checked_gate(action, evaluator, key)
                if module_gate.outcome is Outcome.TRUE
                else module_gate
            )
            results.append(result)
            if result.outcome is not Outcome.TRUE:
                continue
            key = NodeId(module.name, "action", index)
            try:
                name = next(
                    iter(set(action) - {"when", "requires", "after", "refresh"})
                )
                entry = registry.action(name)
                prior = previous.plans.get(key) if previous is not None else None
                if (
                    prior is not None
                    and prior.reusable
                    and not prior.opaque
                    and prior.status is not PlanStatus.SKIP
                    and previous is not None
                    and previous.providers[key] == entry
                    and all(
                        store.get(ref) == previous.facts[ref] for ref in prior.facts
                    )
                ):
                    inspections[key] = previous.inspections[key]
                    plans[key] = prior
                    providers[key] = entry
                    continue
                observations = cast(Observations, context.facts)
                observations.requested.clear()
                observation, plan = inspect_action(
                    entry, deepcopy(action[name]), context
                )
                plan = replace(
                    plan,
                    facts=tuple(
                        dict.fromkeys(
                            plan.facts
                            + tuple(
                                sorted(
                                    observations.requested,
                                    key=lambda ref: (ref.module or "", ref.name),
                                )
                            )
                        )
                    ),
                )
                for ref in plan.facts:
                    fact = store.get(ref)
                    if fact.state is FactState.ERROR:
                        raise ProviderError("{}: {}".format(key, fact.reason))
                inspections[key], plans[key], providers[key] = observation, plan, entry
            except (ValueError, ProviderError, OSError) as exc:
                if not collect_errors:
                    raise ProviderError("{}: {}".format(key, exc)) from exc
                errors[key] = str(exc)
        selections[module.name] = Selection(module_gate, tuple(results))

    def checked_proof(result: Result, key: NodeId, graph: ActionGraph) -> Result:
        try:
            return prove(result, key, graph, completed)
        except ValueError as exc:
            if not collect_errors:
                raise
            errors[key] = str(exc)
            return result

    graph = ActionGraph()
    try:
        graph = build_graph(repository, selections, plans)
    except (ValueError, ProviderError, OSError) as exc:
        if not collect_errors:
            raise
        issues.append("Dependency checks incomplete: {}".format(exc))
    else:
        for name, selection in selections.items():
            module_gate = (
                selection.module
                if name in frozen_modules
                else checked_proof(selection.module, NodeId(name, "start"), graph)
            )
            proven = tuple(
                (
                    result
                    if NodeId(name, "action", index) in frozen
                    else checked_proof(result, NodeId(name, "action", index), graph)
                )
                if module_gate.outcome is Outcome.TRUE
                else module_gate
                for index, result in enumerate(selection.actions)
            )
            selections[name] = Selection(module_gate, proven)
    claims = validate_claims(plans, errors=issues if collect_errors else None)
    return Report(
        MappingProxyType(selections),
        graph,
        MappingProxyType(plans),
        MappingProxyType(inspections),
        MappingProxyType(providers),
        MappingProxyType({ref: store.peek(ref) for ref in store.references()}),
        claims,
        registry.entries(),
        MappingProxyType(errors),
        tuple(issues),
    )
