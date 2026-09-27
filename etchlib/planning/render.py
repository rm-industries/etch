"""Plain-text plans without exposing provider payloads or command environments."""

from typing import Iterable

from etchlib import PLUGIN_API_VERSION
from etchlib.conditions.render import describe_condition
from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.graph.model import NodeId
from etchlib.output import action_lines
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
        "Inspection only: no actions applied.",
    ]
    if verbose:
        lines.extend(
            [
                "Execution: {} jobs; undeclared resource capacities default to one".format(
                    settings.jobs
                ),
                "No installers downloaded or executed.",
                "Fact inspection may run bounded version probes; plugins are trusted Python code.",
            ]
        )
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
    lines.append("")
    if not verbose:
        lines.append("Here's what Etch found:")
        for module in repository.modules:
            selection = report.selections[module.name]
            lines.append("{}:".format(module.name))
            if selection.module.outcome is not Outcome.TRUE:
                detail = describe_condition(module.config.get("when", {}))
                label = (
                    "SKIP" if selection.module.outcome is Outcome.FALSE else "DEFERRED"
                )
                lines.append("  {} — {}".format(label, detail))
                continue
            for index, result in enumerate(selection.actions):
                key = NodeId(module.name, "action", index)
                plan = report.plans.get(key)
                if plan is not None:
                    lines.extend(
                        action_lines(plan.status.value.upper(), plan.description, "  ")
                    )
                else:
                    label = "SKIP" if result.outcome is Outcome.FALSE else "DEFERRED"
                    detail = describe_condition(
                        module.config["actions"][index].get("when", {})
                    )
                    lines.append("  {} — {}".format(label, detail))
                    lines.extend("    " + reason for reason in result.reasons)
            lines.append("")
    else:
        lines.append("Selected modules:")
        for module in repository.modules:
            selection = report.selections[module.name]
            outcome = selection.module.outcome
            lines.append(
                "  {}{}".format(
                    module.name,
                    "" if outcome is Outcome.TRUE else ": " + outcome.value.upper(),
                )
            )
            for index, result in enumerate(selection.actions):
                if result.outcome is Outcome.TRUE:
                    continue
                detail = describe_condition(
                    module.config["actions"][index].get("when", {})
                )
                lines.append(
                    "  {}: {} — {}".format(
                        NodeId(module.name, "action", index),
                        "SKIP" if result.outcome is Outcome.FALSE else "DEFERRED",
                        detail,
                    )
                )
                lines.extend("    " + reason for reason in result.reasons)
    if verbose:
        lines.append("")
        lines.append("Actions (dependency order):")
    shown = 0
    for key in report.graph.order() if verbose else ():
        node = report.graph.node(key)
        plan = report.plans.get(key)
        if plan is None:
            if not verbose:
                continue
            suffix = "" if node.outcome is Outcome.TRUE else " [deferred]"
            if key.kind == "refresh":
                producer = report.plans.get(NodeId(key.module, "action", key.index))
                suffix += " (after successful execution; no refresh during planning)"
                if producer is not None and producer.status.value == "skip":
                    suffix += " [producer skipped]"
            lines.append("  {}{}".format(key, suffix))
            continue
        observation = report.inspections[key]
        shown += 1
        lines.extend(
            action_lines(plan.status.value.upper(), plan.description, "  ", str(key))
        )
        if verbose:
            lines.append(
                "    current: {}{}".format(
                    observation.state.value,
                    "; " + observation.reason if observation.reason else "",
                )
            )
        if verbose:
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
    if verbose and not shown:
        lines.append("  None.")
    if verbose:
        lines.append("")
        lines.append("Ownership: no conflicts among currently active actions.")
        for claim in report.claims:
            lines.append(
                "  {}: {} {}".format(
                    claim.owner, claim.claim.kind.value, claim.claim.path
                )
            )
        lines.append("Facts (unused declarations are not probed):")
        for ref, fact in report.facts.items():
            label = "{}.{}".format(ref.module or "global", ref.name)
            detail = "not requested" if fact is None else fact.state.value
            if fact is not None:
                detail += ": " + (
                    repr(fact.value)
                    if fact.state is FactState.VALUE
                    else str(fact.reason)
                )
            lines.append("  {}: {}".format(label, detail))
    counts = {
        status: sum(plan.status.value == status for plan in report.plans.values())
        for status in ("change", "run", "skip")
    }
    counts["deferred"] = sum(
        result.outcome is Outcome.DEFERRED
        for selection in report.selections.values()
        for result in selection.actions
    )
    summary = (
        ", ".join(
            "{} {}".format(count, status) for status, count in counts.items() if count
        )
        or "no actions"
    )
    lines.append("")
    lines.append("Plan summary: {}.".format(summary))
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
