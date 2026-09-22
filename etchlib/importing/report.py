"""Structural checks and inventory; never load a consumer plugin or probe."""

from pathlib import Path

from etchlib.conditions.schema import validate
from etchlib.config import Module, load_repository
from etchlib.core import core_registry

from .tree import Entry


def validate_module(staging: Path, name: str) -> Module:
    module = load_repository(staging, selected=[name]).modules[0]
    if "when" in module.config:
        validate(module.config["when"])
    for action in module.config.get("actions", []):
        if "when" in action:
            validate(action["when"])
    return module


def inventory(module: Module, consumer: Path, selected: tuple[Entry, ...]) -> list[str]:
    core = {(entry.kind, entry.name) for entry in core_registry().entries()}
    existing = {
        path.parent.name for path in (consumer / "modules").glob("*/module.conf")
    }
    existing.add(module.name)
    lines = [
        "Structural validation only; provider payloads, defaults and runtime state are not checked."
    ]

    def provider(kind: str, name: str, location: str) -> None:
        status = (
            "core"
            if (kind, name) in core
            else "not supplied by core; plugin availability unverified; review/install/declare the required plugin explicitly"
        )
        lines.append("{} {} provider {!r}: {}".format(location, kind, name, status))

    def dependencies(config: dict[str, object], location: str) -> None:
        for field in ("requires", "after"):
            values = config.get(field, [])
            assert isinstance(values, list)
            for dependency in values:
                status = (
                    "present"
                    if dependency in existing
                    else "missing; setup required"
                    if field == "requires"
                    else "absent; ordering warning"
                )
                lines.append(
                    "{} {} {!r}: {}".format(location, field, dependency, status)
                )

    dependencies(module.config, "module")
    for name, declaration in module.config.get("facts", {}).items():
        provider("fact", next(iter(declaration)), "fact {!r}".format(name))
    for index, action in enumerate(module.config.get("actions", [])):
        location = "action[{}]".format(index)
        name = next(iter(set(action) - {"when", "requires", "after", "refresh"}))
        provider("action", name, location)
        dependencies(action, location)
        if name in ("shell", "script", "installer"):
            lines.append("Executable behavior: {} {}".format(location, name))
        if name == "installer" and isinstance(action[name], dict):
            # Do not leak URL credentials or query parameters from arbitrary data.
            from urllib.parse import urlsplit

            url = action[name].get("url")
            if isinstance(url, str):
                try:
                    parsed = urlsplit(url)
                    display = "{}://{}{}".format(
                        parsed.scheme, parsed.hostname or "", parsed.path
                    )
                except ValueError:
                    display = "<invalid URL>"
                lines.append(
                    "Installer URL (credentials/query omitted): {!r}".format(display)
                )
    for entry in selected:
        if entry.executable or entry.path.endswith(".py"):
            lines.append(
                "Executable-content review: {!r}{}".format(
                    entry.path, " (executable bit)" if entry.executable else ""
                )
            )
    lines.append(
        "Any provider may execute code; this inventory is not a safety certification. No imported behavior or plugins were executed. Review files before separately running doctor/plan."
    )
    return lines
