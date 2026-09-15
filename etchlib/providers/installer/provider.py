"""Download a complete installer before running its temporary local copy."""

import tempfile
from pathlib import Path
from typing import Any

from etchlib.providers.commands.runtime import checked, run
from etchlib.providers.contracts import Context
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, Plan, PlanStatus

from .download import download
from .schema import Installer, normalize


class InstallerProvider:
    name = "installer"

    def validate(self, config: Any, context: Context) -> None:
        normalize(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        installer = normalize(config, context)
        return Inspection(
            InspectionState.SATISFIED
            if checked(installer.options, context)
            else InspectionState.UNKNOWN,
            installer,
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        installer: Installer = observation.data
        skip = observation.state is InspectionState.SATISFIED
        options = installer.options
        description = (
            "Check satisfied; skip " if skip else "Download and execute "
        ) + installer.url
        if options.get("description"):
            description = options["description"] + ": " + description
        if not installer.verify:
            description += " (TLS verification disabled)"
        resources: tuple[str, ...] = (
            ("sudo-interactive",) if options.get("sudo", False) and not skip else ()
        )
        if options.get("stdin", False) and not skip:
            resources += ("stdin-interactive",)
        return Plan(
            PlanStatus.SKIP if skip else PlanStatus.RUN,
            description,
            payload=installer,
            network=not skip,
            opaque=not skip,
            elevated=bool(options.get("sudo", False)) and not skip,
            resources=resources,
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        installer: Installer = plan.payload
        if checked(installer.options, context):
            return ApplyResult(False, "Installer check already satisfied")
        if installer.options.get("sudo", False) and not context.elevation_allowed:
            raise ValueError("installer privilege escalation has not been authorized")
        if installer.ca_file is not None:
            installer.ca_file.resolve().relative_to(context.module_root.resolve())
        with tempfile.TemporaryDirectory(prefix="etch-installer-") as directory:
            script = Path(directory) / "installer"
            download(installer, script)
            options = dict(
                installer.options, argv=(installer.shell, str(script)) + installer.args
            )
            run(options, context)
        return ApplyResult(True, "Installer ran: " + installer.url)
