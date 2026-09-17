"""Human-readable doctor results, including origins even when planning fails."""

import platform
from typing import Iterable

from etchlib import PLUGIN_API_VERSION
from etchlib.conditions.results import Outcome
from etchlib.config import Repository
from etchlib.graph.model import NodeId
from etchlib.plugins.metadata import Metadata
from etchlib.providers.registry import Registry

from .doctor import Diagnosis
from .facts import render_facts


def render_doctor(
    repository: Repository,
    registry: Registry,
    plugins: Iterable[Metadata],
    diagnosis: Diagnosis,
) -> str:
    lines = [
        "Doctor: {}".format(repository.root),
        "Runtime: Python {}; {}".format(platform.python_version(), platform.system()),
        "Configuration structure OK: {}".format(repository.root),
        "Selected modules:",
    ]
    lines.extend("  " + module.name for module in repository.modules)
    for plugin in plugins:
        lines.append(
            "Plugin {} {} (API {} compatible): {}".format(
                plugin.name, plugin.version, plugin.api, plugin.root
            )
        )
    lines.append("Registered providers:")
    for entry in registry.entries():
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
    lines.append(render_facts(diagnosis.facts))
    if diagnosis.plan is not None:
        lines.append("Dependencies and destination claims: current snapshot checked.")
        for module, selection in diagnosis.plan.selections.items():
            for index, result in enumerate((selection.module,) + selection.actions):
                if result.outcome is Outcome.DEFERRED:
                    lines.append(
                        "Deferred: {} — {}".format(
                            NodeId(module, "start")
                            if index == 0
                            else NodeId(module, "action", index - 1),
                            "; ".join(result.reasons),
                        )
                    )
    lines.extend("Warning: " + message for message in diagnosis.warnings)
    lines.extend("Error: " + message for message in diagnosis.errors)
    lines.append(
        "Inspection only: no actions applied. Deferred actions need fresh inspection after refresh; opaque commands are not verified. Plugins and fact probes are trusted code."
    )
    lines.append(
        "Doctor {}: {} errors, {} warnings.".format(
            "FAILED" if diagnosis.errors else "OK",
            len(diagnosis.errors),
            len(diagnosis.warnings),
        )
    )
    return "\n".join(lines)
