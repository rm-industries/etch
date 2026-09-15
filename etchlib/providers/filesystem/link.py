"""Module-owned source links with explicit parent creation and relinking."""

from dataclasses import dataclass
from pathlib import Path

from etchlib.config import Module, compose_defaults, destination
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, ClaimKind, PathClaim, Plan, PlanStatus

from .receipts import record
from .state import check_parent, kind


@dataclass(frozen=True)
class Link:
    destination: Path
    source: Path
    create: bool
    relink: bool


def entries(config, context):
    if not isinstance(config, dict) or not config:
        raise ValueError("link expects a nonempty destination-to-source dictionary")
    module = Module(context.module_name, context.module_root, {})
    result = []
    for target, value in config.items():
        options = {"path": value} if isinstance(value, str) else value
        if not isinstance(options, dict) or set(options) - {"path", "create", "relink"}:
            raise ValueError("link entries accept path, create and relink")
        options = compose_defaults(
            "link", context.defaults.get("link", {}), options, ("create", "relink")
        )
        for key in ("create", "relink"):
            if type(options.get(key, False)) is not bool:
                raise ValueError("link {} must be boolean".format(key))
        source = module.asset(options.get("path"))
        result.append(
            Link(
                destination(target, context.repo_root),
                source,
                options.get("create", False),
                options.get("relink", False),
            )
        )
    if len({link.destination for link in result}) != len(result):
        raise ValueError("duplicate normalized link destinations")
    for link in result:
        for other in result:
            if link is not other and link.destination in other.destination.parents:
                raise ValueError("link destinations cannot contain one another")
            if (
                link.destination == other.source
                or link.destination in other.source.parents
            ):
                raise ValueError(
                    "link destination would replace a source in the same action"
                )
    return tuple(result)


def needed(link):
    if not link.source.exists():
        raise ValueError("link source does not exist: {}".format(link.source))
    if link.destination == link.source or link.destination in link.source.parents:
        raise ValueError(
            "link destination would replace its own source: {}".format(link.destination)
        )
    if link.source.is_dir() and link.source in link.destination.parents:
        raise ValueError("link would recursively contain its source")
    check_parent(link.destination, link.create)
    state = kind(link.destination)
    if state == "missing":
        return True
    if state != "link":
        raise ValueError(
            "refusing to replace file or directory: {}".format(link.destination)
        )
    if link.destination.resolve() == link.source:
        return False
    if not link.relink:
        raise ValueError(
            "different or broken link: {} (enable relink)".format(link.destination)
        )
    return True


class LinkProvider:
    name = "link"

    def validate(self, config, context):
        entries(config, context)

    def inspect(self, config, context):
        links = entries(config, context)
        changes = [needed(link) for link in links]
        return Inspection(
            InspectionState.CHANGE if any(changes) else InspectionState.SATISFIED, links
        )

    def plan(self, config, observation, context):
        claims = []
        for link in observation.data:
            claims.append(PathClaim(link.destination))
            if link.create:
                claims.append(
                    PathClaim(link.destination.parent, ClaimKind.SHARED_DIRECTORY)
                )
        return Plan(
            PlanStatus.SKIP
            if observation.state is InspectionState.SATISFIED
            else PlanStatus.CHANGE,
            "Link: " + ", ".join(str(link.destination) for link in observation.data),
            payload=observation.data,
            claims=tuple(claims),
        )

    def apply(self, plan, context):
        for link in plan.payload:
            if (
                destination(str(link.destination), context.repo_root)
                != link.destination
            ):
                raise ValueError("destination parent changed since planning")
            link.source.resolve().relative_to(context.module_root.resolve())
            needed(link)
        changed = False
        for link in plan.payload:
            if not needed(link):
                continue
            if link.create:
                link.destination.parent.mkdir(parents=True, exist_ok=True)
            if kind(link.destination) == "link":
                link.destination.unlink()
            link.destination.symlink_to(link.source)
            record(context.repo_root, link.destination, context.module_name)
            changed = True
        return ApplyResult(
            changed, "Links updated" if changed else "Links already correct"
        )
