"""Resolve hard module dependencies and warning-only missing soft targets."""

from etchlib.conditions.results import Outcome

from .model import GraphError, NodeId


def connect_dependencies(graph, modules, selections, source, requires, after):
    for hard, targets in ((True, requires), (False, after)):
        for target in dict.fromkeys(targets):
            available = (
                target in modules
                and selections[target].module.outcome is not Outcome.FALSE
            )
            if not available:
                message = (
                    "{}: {} target {!r} is missing, unselected or inactive".format(
                        source, "requires" if hard else "after", target
                    )
                )
                if hard:
                    raise GraphError(message)
                graph.warnings.append(message)
                continue
            graph.connect(NodeId(target, "finish"), source)
