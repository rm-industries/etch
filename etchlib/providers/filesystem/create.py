"""Idempotent directory creation, with shared ownership requirements."""

from etchlib.config import destination
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, ClaimKind, PathClaim, Plan, PlanStatus

from .state import directory_needed


class CreateProvider:
    name = "create"

    def validate(self, config, context):
        if not isinstance(config, list) or not config:
            raise ValueError("create expects a nonempty list of directory paths")
        if context.defaults.get(self.name):
            raise ValueError("create does not accept default options")
        paths = [destination(value, context.repo_root) for value in config]
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate create destinations")

    def inspect(self, config, context):
        paths = tuple(destination(value, context.repo_root) for value in config)
        needed = [directory_needed(path) for path in paths]
        return Inspection(
            InspectionState.CHANGE if any(needed) else InspectionState.SATISFIED, paths
        )

    def plan(self, config, observation, context):
        return Plan(
            PlanStatus.SKIP
            if observation.state is InspectionState.SATISFIED
            else PlanStatus.CHANGE,
            "Create directories: " + ", ".join(map(str, observation.data)),
            payload=observation.data,
            claims=tuple(
                PathClaim(path, ClaimKind.SHARED_DIRECTORY) for path in observation.data
            ),
        )

    def apply(self, plan, context):
        paths = plan.payload
        # Preflight the entire action before the first mutation, including old SKIP plans.
        for path in paths:
            if destination(str(path), context.repo_root) != path:
                raise ValueError(
                    "destination parent changed since planning: {}".format(path)
                )
            directory_needed(path)
        changed = False
        for path in paths:
            if directory_needed(path):
                path.mkdir(parents=True, exist_ok=True)
                changed = True
        return ApplyResult(
            changed, "Directories created" if changed else "Directories already present"
        )
