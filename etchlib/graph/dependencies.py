"""Resolve hard module dependencies and warning-only missing soft targets."""

from typing import Iterable, Mapping

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome
from etchlib.config import Module

from .dag import ActionGraph
from .model import GraphError, NodeId


def connect_dependencies(
    graph: ActionGraph,
    modules: Mapping[str, Module],
    selections: Mapping[str, Selection],
    source: NodeId,
    requires: Iterable[str],
    after: Iterable[str],
) -> None:
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
