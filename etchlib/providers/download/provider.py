"""Download a validated upstream asset without executing it."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from etchlib.config import compose_defaults, destination
from etchlib.providers.commands.options import validate_options
from etchlib.providers.commands.runtime import checked
from etchlib.providers.contracts import Context
from etchlib.providers.download.schema import Transfer, normalize_transfer
from etchlib.providers.download.transfer import download
from etchlib.providers.filesystem.state import check_parent, kind
from etchlib.providers.observations import Inspection, InspectionState
from etchlib.providers.plans import ApplyResult, ClaimKind, PathClaim, Plan, PlanStatus

from .receipts import owned_asset, record


@dataclass(frozen=True)
class Asset:
    destination: Path
    transfer: Transfer
    check: Optional[dict[str, str]]
    description: Optional[str]


def normalize(config: Any, context: Context) -> Asset:
    if not isinstance(config, dict):
        raise ValueError("download expects an options dictionary")
    values = compose_defaults(
        "download",
        context.defaults.get("download", {}),
        config,
        ("tls", "download_timeout"),
    )
    if set(values) - {
        "url",
        "destination",
        "check",
        "sha256",
        "tls",
        "download_timeout",
        "description",
    }:
        raise ValueError("unknown download options")
    if "destination" not in values:
        raise ValueError("download requires a destination")
    validate_options(
        {key: values[key] for key in ("check", "description") if key in values}
    )
    transfer = normalize_transfer(
        {
            key: values[key]
            for key in ("url", "sha256", "tls", "download_timeout")
            if key in values
        },
        context,
    )
    return Asset(
        destination(values["destination"], context.repo_root),
        transfer,
        values.get("check"),
        values.get("description"),
    )


def needed(asset: Asset, context: Context) -> bool:
    check_parent(asset.destination, True)
    state = kind(asset.destination)
    if state == "missing":
        return True
    if state != "file":
        raise ValueError("refusing to replace non-file: {}".format(asset.destination))
    previous = owned_asset(context.repo_root, asset.destination, context.module_name)
    if previous is None:
        raise ValueError(
            "refusing to replace unmanaged file: {}".format(asset.destination)
        )
    return (
        previous[0] != asset.transfer.url
        or (asset.transfer.sha256 is not None and previous[1] != asset.transfer.sha256)
        or (asset.check is not None and not checked({"check": asset.check}, context))
    )


class DownloadProvider:
    name = "download"

    def validate(self, config: Any, context: Context) -> None:
        normalize(config, context)

    def inspect(self, config: Any, context: Context) -> Inspection:
        asset = normalize(config, context)
        return Inspection(
            InspectionState.CHANGE
            if needed(asset, context)
            else InspectionState.SATISFIED,
            asset,
        )

    def plan(self, config: Any, observation: Inspection, context: Context) -> Plan:
        asset: Asset = observation.data
        skip = observation.state is InspectionState.SATISFIED
        description = "{} {} → {}".format(
            "Already downloaded" if skip else "Download",
            asset.transfer.url,
            asset.destination,
        )
        if asset.description:
            description = asset.description + ": " + description
        if not asset.transfer.verify:
            description += " (TLS verification disabled)"
        return Plan(
            PlanStatus.SKIP if skip else PlanStatus.CHANGE,
            description,
            payload=asset,
            claims=(
                PathClaim(asset.destination),
                PathClaim(asset.destination.parent, ClaimKind.SHARED_DIRECTORY),
            ),
            network=not skip,
        )

    def apply(self, plan: Plan, context: Context) -> ApplyResult:
        asset: Asset = plan.payload
        if destination(str(asset.destination), context.repo_root) != asset.destination:
            raise ValueError("destination parent changed since planning")
        if not needed(asset, context):
            return ApplyResult(
                False, "Download already present: " + str(asset.destination)
            )
        if asset.transfer.ca_file is not None:
            asset.transfer.ca_file.resolve().relative_to(context.module_root.resolve())
        asset.destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".etch-download-", dir=asset.destination.parent
        ) as directory:
            temporary = Path(directory) / "asset"
            download(asset.transfer, temporary, label="asset")
            # Recheck ownership before replacing an existing destination.
            if not needed(asset, context):
                return ApplyResult(
                    False, "Download already present: " + str(asset.destination)
                )
            if kind(asset.destination) == "missing":
                os.link(temporary, asset.destination)
            else:
                os.replace(temporary, asset.destination)
        record(
            context.repo_root,
            asset.destination,
            context.module_name,
            asset.transfer.url,
        )
        return ApplyResult(True, "Downloaded: " + str(asset.destination))
