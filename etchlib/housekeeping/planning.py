"""Derive lifecycle work from declarations, never from absence in a partial plan."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from etchlib.conditions.module import Selection
from etchlib.conditions.results import Outcome
from etchlib.config import Repository, destination
from etchlib.graph.model import NodeId
from etchlib.providers.filesystem.state import kind
from etchlib.providers.plans import ClaimKind, Plan

from .records import filename, records
from .scope import checked_configuration, removed_module
from .tasks import Task, matches


def claimed(path: Path, plans: Mapping[NodeId, Plan], root: Path) -> bool:
    for plan in plans.values():
        for claim in plan.claims:
            other = destination(str(claim.path), root)
            if path == other or (
                claim.kind is ClaimKind.EXCLUSIVE
                and (path in other.parents or other in path.parents)
            ):
                return True
    return False


@dataclass(frozen=True)
class Batch:
    tasks: tuple[Task, ...]
    configuration: tuple[tuple[Path, bytes], ...] = ()


def inspect(
    repository: Repository,
    selections: Mapping[str, Selection],
    plans: Mapping[NodeId, Plan],
) -> Batch:
    root = repository.root
    if kind(root / ".etch") == "missing":
        return Batch(())
    catalog = (
        repository.catalog if repository.catalog is not None else repository.modules
    )
    available = {module.name for module in catalog}
    declared: set[Path] = set()
    downloads: dict[str, Path] = {}
    uncertain: set[str] = set()
    for module in catalog:
        try:
            for action in module.config.get("actions", []):
                if "link" in action:
                    if not isinstance(action["link"], dict):
                        uncertain.add(module.name)
                        continue
                    declared.update(
                        destination(value, root) for value in action["link"]
                    )
                if (
                    isinstance(action.get("download"), dict)
                    and "destination" in action["download"]
                ):
                    target = destination(action["download"]["destination"], root)
                    downloads[filename(target)] = target
        except ValueError:
            uncertain.add(module.name)
    eligible = {
        name
        for name, selection in selections.items()
        if selection.module.outcome is Outcome.TRUE
        and all(result.outcome is not Outcome.DEFERRED for result in selection.actions)
    } - uncertain
    tasks = []
    removed_owners: dict[str, bool] = {}
    for namespace in ("links", "downloads"):
        for record in records(root, namespace):
            data = record.data
            if data is None:
                tasks.append(Task(record, "invalid", "etch housekeeping"))
                continue
            schema = data.get("schema")
            if type(schema) is int and schema > 1:
                continue
            owner = data.get("module")
            if (
                not isinstance(owner, str)
                or Path(owner).name != owner
                or owner in (".", "..")
            ):
                tasks.append(Task(record, "invalid", "etch housekeeping"))
                continue
            if namespace == "downloads" and (
                not isinstance(data.get("url"), str)
                or not isinstance(data.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", data["sha256"]) is None
            ):
                tasks.append(Task(record, "invalid", owner))
                continue
            raw_target = data.get("destination")
            if namespace == "downloads" and raw_target is None:
                if record.path.name in downloads:
                    tasks.append(
                        Task(record, "upgrade", owner, downloads[record.path.name])
                    )
                elif (
                    repository.full_selection
                    and repository.catalog is not None
                    and not uncertain
                ):
                    tasks.append(Task(record, "legacy", owner))
                continue
            if not isinstance(raw_target, str) or not Path(raw_target).is_absolute():
                tasks.append(Task(record, "invalid", owner))
                continue
            target = Path(raw_target)
            if record.path.name != filename(target):
                tasks.append(Task(record, "invalid", owner))
                continue
            if namespace == "downloads":
                if kind(target) == "missing":
                    tasks.append(Task(record, "missing", owner, target))
                continue
            if type(schema) is not int or schema != 1:
                tasks.append(Task(record, "invalid", owner))
                continue
            if not matches(record, target):
                tasks.append(Task(record, "stale", owner, target))
                continue
            if owner not in removed_owners:
                removed_owners[owner] = (
                    repository.full_selection
                    and owner not in available
                    and removed_module(root, owner)
                )
            removed = removed_owners[owner]
            if (
                repository.catalog is not None
                and (owner in eligible or removed)
                and target not in declared
                and not uncertain
                and not claimed(target, plans, root)
            ):
                tasks.append(
                    Task(record, "retire", owner, target, removed_owner=removed)
                )
    return Batch(tuple(tasks), checked_configuration(repository) if tasks else ())
