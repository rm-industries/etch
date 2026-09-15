"""Rebuild validation for all currently active actions; never apply a provider."""

from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Optional

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.graph.builder import build_graph
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import FactLink, NodeId
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import plan_action
from etchlib.providers.observations import FactRef, FactResult
from etchlib.providers.plans import Plan
from etchlib.providers.registry import Registry

from .claims import OwnedClaim, OwnershipError, validate_claims


@dataclass(frozen=True)
class Snapshot:
    graph: ActionGraph
    plans: Mapping[NodeId, Plan]
    claims: tuple[OwnedClaim, ...]


def validate_snapshot(
    repository: Repository,
    selections: Mapping[str, Selection],
    registry: Registry,
    facts: Optional[Mapping[FactRef, FactResult]] = None,
    fact_links: Iterable[FactLink] = (),
    elevated_actions: Iterable[NodeId] = (),
) -> Snapshot:
    """Fresh provider validation/inspection/planning, graph and ownership checks.

    Call again after facts change and conditions are reevaluated. No previous plan
    is accepted as proof that a newly activated action is valid.
    """
    plans = {}
    allowed = set(elevated_actions)
    if set(selections) != {module.name for module in repository.modules}:
        raise OwnershipError("selections must cover exactly the selected modules")
    for module in repository.modules:
        selection = selections[module.name]
        actions = module.config.get("actions", [])
        if len(selection.actions) != len(actions):
            raise OwnershipError(
                "{}: incorrect action selection count".format(module.name)
            )
        if selection.module.outcome is not Outcome.TRUE:
            continue
        for index, (action, result) in enumerate(zip(actions, selection.actions)):
            if result.outcome is not Outcome.TRUE:
                continue
            key = NodeId(module.name, "action", index)
            providers = set(action) - {"when", "requires", "after", "refresh"}
            if len(providers) != 1:
                raise OwnershipError(
                    "{}: action must declare exactly one provider".format(key)
                )
            name = next(iter(providers))
            context = Context(
                repository.root,
                module.root,
                module.name,
                MappingProxyType(deepcopy(facts or {})),
                MappingProxyType(deepcopy(repository.defaults.get("defaults", {}))),
            )
            plan = plan_action(registry.action(name), deepcopy(action[name]), context)
            if plan.elevated and key not in allowed:
                raise OwnershipError(
                    "{}: privilege escalation has not been authorized".format(key)
                )
            plans[key] = plan
    graph = build_graph(repository, selections, plans, fact_links)
    claims = validate_claims(plans)
    return Snapshot(graph, MappingProxyType(plans), claims)
