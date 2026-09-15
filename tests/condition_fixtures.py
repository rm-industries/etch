from pathlib import Path
from typing import Any

from etchlib.conditions.evaluator import Evaluator
from etchlib.facts.core import core_registry
from etchlib.facts.store import FactStore
from etchlib.providers.contracts import Context
from etchlib.providers.observations import FactRef, FactResult
from etchlib.providers.registry import Origin


class Observations:
    name = "test_observation"

    def __init__(self) -> None:
        self.values: dict[str, FactResult] = {}
        self.calls: list[str] = []

    def validate(self, config: Any, context: Context) -> None:
        pass

    def gather(self, config: Any, context: Context) -> FactResult:
        self.calls.append(config)
        return self.values[config]


class ConditionFixture:
    def setUp(self) -> None:
        self.context = Context(Path("/repo"), Path("/repo/modules/demo"), "demo", {})
        self.registry = core_registry()
        self.observations = Observations()
        self.registry.register(Origin("test", "1"), facts=[self.observations])
        self.store = FactStore(self.registry)
        for name in ("os", "distro", "arch"):
            self.store.declare(FactRef(None, name), name, {}, self.context)
        self.evaluator = Evaluator(self.store, self.context)

    def fact(self, name: str, value: FactResult) -> FactRef:
        self.observations.values[name] = value
        ref = FactRef("demo", name)
        self.store.declare(ref, "test_observation", name, self.context)
        return ref
