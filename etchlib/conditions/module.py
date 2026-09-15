"""Apply one evaluator to a module gate and its ordered action gates."""

from dataclasses import dataclass
from typing import Tuple

from .results import ConditionError, Outcome, Result
from .schema import validate


@dataclass(frozen=True)
class Selection:
    module: Result
    actions: Tuple[Result, ...]


def select_module(module, evaluator) -> Selection:
    if (
        evaluator.context.module_name != module.name
        or evaluator.context.module_root != module.root
    ):
        raise ConditionError(
            "module selection requires an evaluator scoped to that module"
        )
    actions = module.config.get("actions", [])
    # Syntax errors remain visible even in branches that do not apply here.
    for config in [module.config] + actions:
        if "when" in config:
            validate(config["when"])
    gate = (
        evaluator.evaluate(module.config["when"])
        if "when" in module.config
        else Result(Outcome.TRUE)
    )
    if gate.outcome is not Outcome.TRUE:
        return Selection(gate, tuple(gate for _ in actions))
    results = tuple(
        evaluator.evaluate(action["when"]) if "when" in action else Result(Outcome.TRUE)
        for action in actions
    )
    return Selection(gate, results)
