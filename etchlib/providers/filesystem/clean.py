"""Conservative cleanup of receipt-backed broken or explicitly retired links."""
from dataclasses import dataclass

from etchlib.config import destination
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, PathClaim, Plan, PlanStatus
from .receipts import identity, owned
from .state import kind


@dataclass(frozen=True)
class Removal:
    path: object
    proof: dict
    retired: bool


def options(config, context):
    value = {"paths": config} if isinstance(config, list) else config
    if not isinstance(value, dict) or set(value) - {"paths", "obsolete"}:
        raise ValueError("clean expects directories or {paths, obsolete}")
    paths, obsolete = value.get("paths"), value.get("obsolete", [])
    if not isinstance(paths, list) or not paths or not isinstance(obsolete, list):
        raise ValueError("clean requires a nonempty paths list and optional obsolete list")
    roots = tuple(destination(path, context.repo_root) for path in paths)
    retired = tuple(destination(path, context.repo_root) for path in obsolete)
    if len(set(roots)) != len(roots) or len(set(retired)) != len(retired):
        raise ValueError("duplicate clean paths")
    if any(path.parent not in roots for path in retired):
        raise ValueError("obsolete destinations must be immediate children of selected directories")
    if context.defaults.get("clean"):
        raise ValueError("clean does not accept defaults")
    return roots, set(retired)


def broken(path):
    try:
        path.stat()
    except FileNotFoundError:
        return True
    # Permission errors and loops are not proof of a missing target.
    return False


class CleanProvider:
    name = "clean"

    def validate(self, config, context):
        options(config, context)

    def inspect(self, config, context):
        roots, retired = options(config, context)
        removals = []
        for root in roots:
            state = kind(root)
            if state == "missing":
                continue
            if state != "directory":
                raise ValueError("clean roots must be real directories, not files or symlinks: {}".format(root))
            for path in sorted(root.iterdir()):
                if kind(path) != "link" or not owned(context.repo_root, path):
                    continue
                if path in retired or broken(path):
                    removals.append(Removal(path, identity(path), path in retired))
        return Inspection(InspectionState.CHANGE if removals else InspectionState.SATISFIED, tuple(removals))

    def plan(self, config, observation, context):
        return Plan(PlanStatus.CHANGE if observation.data else PlanStatus.SKIP,
                    "Remove managed links: " + ", ".join(str(item.path) for item in observation.data)
                    if observation.data else "No proven obsolete or broken managed links",
                    payload=observation.data, claims=tuple(PathClaim(item.path) for item in observation.data))

    def apply(self, plan, context):
        pending = []
        for item in plan.payload:
            if destination(str(item.path), context.repo_root) != item.path:
                raise ValueError("clean destination parent changed since planning")
            if kind(item.path) == "missing":
                continue
            if not owned(context.repo_root, item.path) or identity(item.path) != item.proof:
                raise ValueError("managed link changed since planning: {}".format(item.path))
            if not item.retired and not broken(item.path):
                continue
            pending.append(item)
        changed = False
        for item in pending:
            if not owned(context.repo_root, item.path) or identity(item.path) != item.proof:
                raise ValueError("managed link changed before removal")
            if not item.retired and not broken(item.path):
                continue
            item.path.unlink()
            changed = True
        return ApplyResult(changed, "Managed links removed" if changed else "No managed links removed")
