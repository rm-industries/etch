from pathlib import Path
from typing import Any, Optional

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome, Result
from etchlib.config import Module, Repository
from etchlib.graph.model import NodeId
from etchlib.providers.plans import Plan, PlanStatus


def module(
    name: str, actions: Optional[list[dict[str, Any]]] = None, **options: Any
) -> Module:
    return Module(
        name,
        Path("/repo/modules") / name,
        dict(
            {"actions": actions if actions is not None else [{"test": {}}]}, **options
        ),
    )


def inputs(
    *modules: Module,
) -> tuple[Repository, dict[str, Selection], dict[NodeId, Plan]]:
    repository = Repository(Path("/repo"), modules, {})
    selections = {
        m.name: Selection(
            Result(Outcome.TRUE),
            tuple(Result(Outcome.TRUE) for _ in m.config["actions"]),
        )
        for m in modules
    }
    plans = {
        NodeId(m.name, "action", i): Plan(PlanStatus.CHANGE, "test")
        for m in modules
        for i, _ in enumerate(m.config["actions"])
    }
    return repository, selections, plans
