"""Build one graph snapshot from selected modules and normalized provider plans."""
from etchlib.conditions.results import Outcome
from etchlib.facts.core import BUILTINS
from etchlib.providers.observations import FactRef
from .dag import ActionGraph
from .dependencies import connect_dependencies
from .model import GraphError, Node, NodeId


def build_graph(repository, selections, plans=None, fact_links=()):
    plans = dict(plans or {})
    modules = {module.name: module for module in repository.modules}
    if set(modules) != set(selections):
        raise GraphError("condition selections must cover exactly the selected modules")
    declared = {FactRef(None, name) for name in BUILTINS}
    declared.update(FactRef(module.name, name) for module in modules.values()
                    for name in module.config.get("facts", {}))
    graph = ActionGraph()
    dependencies, consumers = [], {}
    used_plans = set()
    for module in repository.modules:
        selected = selections[module.name]
        actions = module.config.get("actions", [])
        if len(selected.actions) != len(actions):
            raise GraphError("{}: condition selection has the wrong action count".format(module.name))
        if selected.module.outcome is not Outcome.TRUE and any(result.outcome is not selected.module.outcome for result in selected.actions):
            raise GraphError("{}: action outcomes must preserve an inactive or deferred module gate".format(module.name))
        if selected.module.outcome is Outcome.FALSE:
            continue
        start, finish = NodeId(module.name, "start"), NodeId(module.name, "finish")
        graph.add(Node(start, selected.module.outcome))
        consumers[start] = set(selected.module.waiting)
        if consumers[start] - declared:
            raise GraphError("{}: undeclared module condition facts".format(start))
        tails = [start]
        if selected.module.outcome is Outcome.TRUE:
            dependencies.append((start, module.config.get("requires", []), module.config.get("after", [])))
        for index, (action, selection) in enumerate(zip(actions, selected.actions)):
            if selection.outcome is Outcome.FALSE:
                continue
            key = NodeId(module.name, "action", index)
            plan = plans.get(key)
            if plan is not None:
                used_plans.add(key)
            graph.add(Node(key, selection.outcome, plan))
            for tail in tails:
                graph.connect(tail, key)
            tails = [key]
            if selected.module.outcome is Outcome.TRUE and selection.outcome is Outcome.TRUE:
                dependencies.append((key, tuple(action.get("requires", [])) + (plan.requires if plan else ()),
                                     tuple(action.get("after", [])) + (plan.after if plan else ())))
            inputs = set(selection.waiting) | set(plan.facts if plan else ())
            refresh = set(FactRef(module.name, name) for name in action.get("refresh", []))
            refresh.update(plan.refresh if plan else ())
            if (inputs | refresh) - declared:
                raise GraphError("{}: undeclared fact references: {}".format(key, (inputs | refresh) - declared))
            consumers[key] = inputs
            # Preserve declaration order, including provider-derived refresh metadata.
            refresh_order = [FactRef(module.name, name) for name in action.get("refresh", [])]
            refresh_order.extend(plan.refresh if plan else ())
            for ref in dict.fromkeys(refresh_order):
                refresh_key = NodeId(module.name, "refresh", index, ref)
                graph.add(Node(refresh_key, selection.outcome))
                graph.connect(key, refresh_key)
                tails.append(refresh_key)
        graph.add(Node(finish, selected.module.outcome))
        for tail in tails:
            graph.connect(tail, finish)
    if set(plans) - used_plans:
        raise GraphError("provider plans reference inactive or unknown actions")
    for source, requires, after in dependencies:
        connect_dependencies(graph, modules, selections, source, requires, after)
    for link in fact_links:
        if link.producer.kind != "action" or link.consumer.kind not in ("action", "start"):
            raise GraphError("fact links require an action producer and action/module-gate consumer")
        graph.node(link.producer)
        graph.node(link.consumer)
        if link.fact not in consumers[link.consumer]:
            raise GraphError("{} does not consume {!r}".format(link.consumer, link.fact))
        refresh = NodeId(link.producer.module, "refresh", link.producer.index, link.fact)
        graph.connect(refresh, link.consumer)
    graph.order()  # Validate every snapshot before exposing it to an executor.
    return graph
