"""Provider lifecycle for sequential imperative command entries."""
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus
from .runtime import checked, preflight, run
from .schema import normalize


class CommandProvider:
    def __init__(self, name):
        if name not in ("shell", "script"):
            raise ValueError("unsupported command provider")
        self.name = name

    def validate(self, config, context):
        normalize(self.name, config, context)

    def inspect(self, config, context):
        entries = normalize(self.name, config, context)
        ready = []
        for options in entries:
            if not checked(options, context):
                preflight(options, context)
                ready.append(options)
        return Inspection(InspectionState.UNKNOWN if ready else InspectionState.SATISFIED, tuple(ready))

    def plan(self, config, observation, context):
        entries = observation.data
        elevated = any(item.get("sudo", False) for item in entries)
        interactive = any(item.get("stdin", False) for item in entries)
        resources = (("sudo-interactive",) if elevated else ()) + (("stdin-interactive",) if interactive else ())
        return Plan(PlanStatus.RUN if entries else PlanStatus.SKIP,
                    "; ".join(item.get("description", "Run " + self.name) for item in entries) if entries else "Checks already satisfied",
                    payload=entries, resources=resources, elevated=elevated, opaque=bool(entries))

    def apply(self, plan, context):
        for item in plan.payload:
            if not checked(item, context):
                preflight(item, context)
                if item.get("sudo", False) and not context.elevation_allowed:
                    raise ValueError("command privilege escalation has not been authorized")
        changed = False
        for item in plan.payload:
            if not checked(item, context):
                preflight(item, context)
                run(item, context)
                changed = True
        return ApplyResult(changed, "Commands ran" if changed else "Checks already satisfied")
