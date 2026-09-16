"""Provisional gates and proof that unresolved observations have future producers."""

from dataclasses import replace
from typing import Any, Collection, Mapping

from etchlib.conditions.evaluator import Evaluator
from etchlib.conditions.results import ConditionError, Outcome, Result
from etchlib.graph.dag import ActionGraph
from etchlib.graph.model import NodeId


def gate(config: Mapping[str, Any], evaluator: Evaluator) -> Result:
    if "when" in config:
        return evaluator.evaluate(config["when"], require_evidence=False)
    return Result(Outcome.TRUE)


def prove(
    result: Result, key: NodeId, graph: ActionGraph, completed: Collection[NodeId]
) -> Result:
    if result.outcome is not Outcome.DEFERRED:
        return result
    finished = {str(node) for node in completed}
    evidence = {
        ref: producer
        for ref, producer in graph.earlier_refresh(key).items()
        if producer not in finished
    }
    missing = [ref for ref in result.waiting if ref not in evidence]
    if missing:
        raise ConditionError(
            "{}: unresolved condition {}; no earlier producer/refresh path remains: {}".format(
                key,
                ", ".join("{}.{}".format(ref.module, ref.name) for ref in missing),
                "; ".join(result.reasons),
            )
        )
    return replace(
        result,
        reasons=result.reasons
        + tuple("waiting for {}".format(evidence[ref]) for ref in result.waiting),
    )
