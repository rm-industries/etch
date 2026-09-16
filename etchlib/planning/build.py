"""Inspect active actions, then prove every deferred gate against the graph."""

from copy import deepcopy
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping, Optional

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.module import Selection
from etchlib.conditions.results import ConditionError, Outcome, Result
from etchlib.conditions.schema import validate
from etchlib.config import Repository
from etchlib.facts.repository import repository_facts
from etchlib.graph.builder import build_graph
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import NodeId
from etchlib.ownership.claims import OwnedClaim, validate_claims
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import inspect_action
from etchlib.providers.observations import FactRef, FactResult, FactState, Inspection
from etchlib.providers.plans import Plan
from etchlib.providers.registry import Registration, Registry

from .facts import Observations


@dataclass(frozen=True)
class Report:
    selections: Mapping[str, Selection]
    graph: ActionGraph
    plans: Mapping[NodeId, Plan]
    inspections: Mapping[NodeId, Inspection]
    providers: Mapping[NodeId, Registration]
    facts: Mapping[FactRef, Optional[FactResult]]
    claims: tuple[OwnedClaim, ...]
    registrations: tuple[Registration, ...]


def _gate(config: Mapping[str, Any], evaluator: Evaluator) -> Result:
    # Unknown gates remain uninspected until graph evidence is available. They
    # are not accepted as valid deferrals until _prove has checked the graph.
    if "when" in config:
        return evaluator.evaluate(config["when"], require_evidence=False)
    return Result(Outcome.TRUE)


def _prove(result: Result, key: NodeId, graph: ActionGraph) -> Result:
    if result.outcome is not Outcome.DEFERRED:
        return result
    evidence = graph.earlier_refresh(key)
    missing = [ref for ref in result.waiting if ref not in evidence]
    if missing:
        raise ConditionError(
            "{}: unresolved condition {}; no earlier producer/refresh path".format(
                key, ", ".join("{}.{}".format(ref.module, ref.name) for ref in missing)
            )
        )
    return replace(
        result,
        reasons=result.reasons
        + tuple("waiting for {}".format(evidence[ref]) for ref in result.waiting),
    )


def plan_repository(repository: Repository, registry: Registry) -> Report:
    store = repository_facts(repository, registry)
    selections, plans, inspections, providers = {}, {}, {}, {}
    for module in repository.modules:
        actions = module.config.get("actions", [])
        for config in [module.config] + actions:
            if "when" in config:
                validate(config["when"])
        context = Context(
            repository.root,
            module.root,
            module.name,
            Observations(store),
            MappingProxyType(deepcopy(repository.defaults.get("defaults", {}))),
        )
        evaluator = Evaluator(store, context)
        gate = _gate(module.config, evaluator)
        results = []
        for index, action in enumerate(actions):
            result = _gate(action, evaluator) if gate.outcome is Outcome.TRUE else gate
            results.append(result)
            if result.outcome is not Outcome.TRUE:
                continue
            key = NodeId(module.name, "action", index)
            name = next(iter(set(action) - {"when", "requires", "after", "refresh"}))
            entry = registry.action(name)
            observation, plan = inspect_action(entry, deepcopy(action[name]), context)
            for ref in plan.facts:
                fact = store.get(ref)
                if fact.state is FactState.ERROR:
                    raise ProviderError("{}: {}".format(key, fact.reason))
            inspections[key], plans[key], providers[key] = observation, plan, entry
        selections[module.name] = Selection(gate, tuple(results))
    graph = build_graph(repository, selections, plans)
    for name, selection in selections.items():
        gate = _prove(selection.module, NodeId(name, "start"), graph)
        proven = tuple(
            _prove(result, NodeId(name, "action", index), graph)
            if gate.outcome is Outcome.TRUE
            else gate
            for index, result in enumerate(selection.actions)
        )
        selections[name] = Selection(gate, proven)
    claims = validate_claims(plans)
    return Report(
        MappingProxyType(selections),
        graph,
        MappingProxyType(plans),
        MappingProxyType(inspections),
        MappingProxyType(providers),
        MappingProxyType({ref: store.peek(ref) for ref in store.references()}),
        claims,
        registry.entries(),
    )
