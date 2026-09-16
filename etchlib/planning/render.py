"""Plain-text plans without exposing provider payloads or command environments."""

from typing import Iterable

from etchlib import PLUGIN_API_VERSION
from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.graph.model import NodeId
from etchlib.plugins.metadata import Metadata
from etchlib.providers.observations import FactState
from etchlib.scheduling.resources import options, requirements

from .build import Report


def render_plan(
    repository: Repository,
    report: Report,
    plugins: Iterable[Metadata] = (),
    verbose: bool = False,
) -> str:
    settings = options(repository.defaults.get("execution", {}))
    lines = [
        "Plan: {}".format(repository.root),
        "Execution: {} jobs; undeclared resource capacities default to one".format(
            settings.jobs
        ),
        "Inspection only: no actions applied, installers downloaded or executed.",
        "Fact inspection may run bounded version probes; plugins are trusted Python code.",
    ]
    for name, capacity in settings.capacities.items():
        lines.append("Resource {}: capacity {}".format(name, capacity))
    for plugin in plugins:
        lines.append(
            "Plugin {} {}: API {} compatible".format(
                plugin.name, plugin.version, plugin.api
            )
        )
    if verbose:
        lines.append("Registered providers:")
        for entry in report.registrations:
            lines.append(
                "  {} {}: {} {} {}; API {} compatible".format(
                    entry.kind,
                    entry.name,
                    "core" if entry.origin.core else "plugin",
                    entry.origin.name,
                    entry.origin.version,
                    PLUGIN_API_VERSION,
                )
            )
    lines.append("Selected modules:")
    for module in repository.modules:
        selection = report.selections[module.name]
        lines.append("  {}: {}".format(module.name, selection.module.outcome.value))
        for index, result in enumerate(selection.actions):
            if result.outcome is Outcome.TRUE:
                continue
            label = (
                "SKIP (condition false)"
                if result.outcome is Outcome.FALSE
                else "DEFERRED"
            )
            lines.append("  {}: {}".format(NodeId(module.name, "action", index), label))
            lines.extend("    " + reason for reason in result.reasons)
    lines.append("Dependency order (current snapshot):")
    for key in report.graph.order():
        node = report.graph.node(key)
        plan = report.plans.get(key)
        if plan is None:
            suffix = "" if node.outcome is Outcome.TRUE else " [deferred]"
            if key.kind == "refresh":
                producer = report.plans.get(NodeId(key.module, "action", key.index))
                suffix += " (after successful execution; no refresh during planning)"
                if producer is not None and producer.status.value == "skip":
                    suffix += " [producer skipped]"
            lines.append("  {}{}".format(key, suffix))
            continue
        observation = report.inspections[key]
        lines.append(
            "  {}: {} — {}".format(key, plan.status.value.upper(), plan.description)
        )
        lines.append(
            "    current: {}{}".format(
                observation.state.value,
                "; " + observation.reason if observation.reason else "",
            )
        )
        network = (
            "yes" if plan.network else "unknown" if plan.opaque else "not declared"
        )
        lines.append(
            "    network: {}; opaque execution: {}; elevation: {}".format(
                network,
                "yes" if plan.opaque else "no",
                "required (not authorized by planning)" if plan.elevated else "no",
            )
        )
        resources = requirements(plan)
        if resources:
            lines.append("    resources: " + ", ".join(sorted(resources)))
        if verbose:
            entry = report.providers[key]
            origin = entry.origin
            lines.append(
                "    provider: {} ({}) from {} {} {}; API {} compatible".format(
                    entry.name,
                    entry.kind,
                    "core" if origin.core else "plugin",
                    origin.name,
                    origin.version,
                    PLUGIN_API_VERSION,
                )
            )
    lines.append("Ownership: no conflicts among currently active actions.")
    for claim in report.claims:
        lines.append(
            "  {}: {} {}".format(claim.owner, claim.claim.kind.value, claim.claim.path)
        )
    lines.append("Facts (unused declarations are not probed):")
    for ref, fact in report.facts.items():
        label = "{}.{}".format(ref.module or "global", ref.name)
        detail = "not requested" if fact is None else fact.state.value
        if fact is not None:
            detail += ": " + (
                repr(fact.value) if fact.state is FactState.VALUE else str(fact.reason)
            )
        lines.append("  {}: {}".format(label, detail))
    lines.extend("Warning: " + warning for warning in report.graph.warnings)
    if any(
        result.outcome is Outcome.DEFERRED
        for selection in report.selections.values()
        for result in (selection.module,) + selection.actions
    ):
        lines.append(
            "Deferred actions require fresh conditions, provider validation and ownership checks after refresh."
        )
    return "\n".join(lines)
