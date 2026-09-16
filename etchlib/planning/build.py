"""Inspect active actions, then prove every deferred gate against the graph."""

from copy import deepcopy
from types import MappingProxyType
from typing import Collection, Optional

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome
from etchlib.conditions.schema import validate
from etchlib.config import Repository
from etchlib.facts.repository import repository_facts
from etchlib.facts.store import FactStore
from etchlib.graph.builder import build_graph
from etchlib.graph.model import NodeId
from etchlib.ownership.claims import validate_claims
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import inspect_action
from etchlib.providers.observations import FactState
from etchlib.providers.registry import Registry

from .conditions import gate, prove
from .context import provider_context
from .model import Report as Report


def plan_repository(
    repository: Repository,
    registry: Registry,
    *,
    store: Optional[FactStore] = None,
    previous: Optional[Report] = None,
    completed: Collection[NodeId] = (),
) -> Report:
    if completed and previous is None:
        raise ValueError("completed actions require their previous snapshot")
    store = store if store is not None else repository_facts(repository, registry)
    selections, plans, inspections, providers = {}, {}, {}, {}
    for module in repository.modules:
        actions = module.config.get("actions", [])
        for config in [module.config] + actions:
            if "when" in config:
                validate(config["when"])
        context = provider_context(repository, module, store)
        evaluator = Evaluator(store, context)
        module_gate = (
            previous.selections[module.name].module
            if previous is not None
            and any(key.module == module.name for key in completed)
            else gate(module.config, evaluator)
        )
        results = []
        for index, action in enumerate(actions):
            key = NodeId(module.name, "action", index)
            if key in completed and previous is not None:
                results.append(previous.selections[module.name].actions[index])
                inspections[key] = previous.inspections[key]
                plans[key] = previous.plans[key]
                providers[key] = previous.providers[key]
                continue
            result = (
                gate(action, evaluator)
                if module_gate.outcome is Outcome.TRUE
                else module_gate
            )
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
        selections[module.name] = Selection(module_gate, tuple(results))
    graph = build_graph(repository, selections, plans)
    for name, selection in selections.items():
        module_gate = prove(selection.module, NodeId(name, "start"), graph, completed)
        proven = tuple(
            prove(result, NodeId(name, "action", index), graph, completed)
            if module_gate.outcome is Outcome.TRUE
            else module_gate
            for index, result in enumerate(selection.actions)
        )
        selections[name] = Selection(module_gate, proven)
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
