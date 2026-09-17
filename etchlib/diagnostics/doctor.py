"""Validate declarations and the current plan, preserving probe diagnostics."""

import platform
import sys
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from etchlib.config import Repository
from etchlib.execution.validation import validate_refresh
from etchlib.facts.repository import repository_facts
from etchlib.graph.model import NodeId
from etchlib.planning.build import plan_repository
from etchlib.planning.context import provider_context
from etchlib.planning.model import Report
from etchlib.providers.errors import ProviderError
from etchlib.providers.lifecycle import validate_action
from etchlib.providers.observations import FactRef, FactResult, FactState
from etchlib.providers.registry import Registry
from etchlib.scheduling.resources import requirements

from .facts import gather, label


@dataclass(frozen=True)
class Diagnosis:
    facts: dict[FactRef, FactResult]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    plan: Optional[Report]


def diagnose(repository: Repository, registry: Registry) -> Diagnosis:
    errors: list[str] = []
    warnings: list[str] = []
    if sys.version_info < (3, 9):
        errors.append(
            "Python 3.9 or newer is required; select a supported interpreter."
        )
    if platform.system() not in ("Linux", "Darwin"):
        errors.append(
            "Unsupported platform {!r}; use Linux or macOS.".format(platform.system())
        )
    store = repository_facts(repository, registry)
    facts = gather(store)
    for ref, result in facts.items():
        if result.state is FactState.ERROR:
            errors.append(
                "{}: {}; check the declaration and probe command.".format(
                    label(ref), result.reason
                )
            )
        elif result.state is FactState.UNAVAILABLE and ref.module is not None:
            warnings.append(
                "{}: {}; check the configured path, PATH or environment if required.".format(
                    label(ref), result.reason
                )
            )
    # Validate schemas even behind false/deferred conditions, without inspection.
    for module in repository.modules:
        context = provider_context(repository, module, store)
        for index, action in enumerate(module.config.get("actions", [])):
            name = next(iter(set(action) - {"when", "requires", "after", "refresh"}))
            try:
                validate_action(registry.action(name), deepcopy(action[name]), context)
            except (ValueError, ProviderError, OSError) as exc:
                errors.append(
                    "{}: {}".format(NodeId(module.name, "action", index), exc)
                )
    report = None
    try:
        validate_refresh(repository, store)
        report = plan_repository(repository, registry, store=store)
        for plan in report.plans.values():
            requirements(plan)
        warnings.extend(report.graph.warnings)
        for claim in report.claims:
            path = claim.claim.path
            if path.is_symlink() and not path.exists():
                warnings.append(
                    "{}: broken link {}; review its target or the planned repair/removal.".format(
                        claim.owner, path
                    )
                )
    except (ValueError, ProviderError, OSError) as exc:
        errors.append("Current plan: {}".format(exc))
    return Diagnosis(facts, tuple(errors), tuple(warnings), report)
