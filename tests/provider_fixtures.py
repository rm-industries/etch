"""Small stateful providers for contract tests, not shipped integrations."""
from etchlib.config import compose_defaults
from etchlib.providers.observations import FactRef, FactResult, FactState, Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, PathClaim, Plan, PlanStatus


class MemoryAction:
    name = "memory"

    def __init__(self):
        self.value = None
        self.calls = []

    def validate(self, config, context):
        self.calls.append("validate")
        if not isinstance(config, dict) or "value" not in config:
            raise ValueError("value is required")

    def inspect(self, config, context):
        self.calls.append("inspect")
        state = InspectionState.SATISFIED if self.value == config["value"] else InspectionState.CHANGE
        return Inspection(state, self.value)

    def plan(self, config, observation, context):
        self.calls.append("plan")
        options = compose_defaults(self.name, {"quiet": True}, config, ("quiet",))
        status = PlanStatus.SKIP if observation.state is InspectionState.SATISFIED else PlanStatus.CHANGE
        fact = FactRef(context.module_name, "installed")
        return Plan(status, "Reconcile memory", payload=options["value"],
                    requires=("base",), after=("optional",), facts=(fact,),
                    claims=(PathClaim(context.module_root / "config"),),
                    refresh=(fact,), resources=("application:memory",))

    def apply(self, plan, context):
        self.calls.append("apply")
        changed = self.value != plan.payload
        self.value = plan.payload
        return ApplyResult(changed, "Reconciled memory")


class MemoryFact:
    name = "memory_value"

    def validate(self, config, context):
        if not isinstance(config, dict):
            raise ValueError("expected dictionary")

    def gather(self, config, context):
        return FactResult(FactState.VALUE, config.get("value"))
