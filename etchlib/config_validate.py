"""Static validation for a consumer's modules and profiles."""

from pathlib import Path

from etchlib.conditions.schema import validate as validate_condition
from etchlib.config import load_repository


def validate_repository(root: Path) -> None:
    """Validate declared structure and gates without loading plugins or probing facts."""
    repository = load_repository(root)
    for module in repository.modules:
        if "when" in module.config:
            validate_condition(module.config["when"])
        for action in module.config.get("actions", []):
            if "when" in action:
                validate_condition(action["when"])
        for fact in module.config.get("facts", {}).values():
            for alternative in fact if isinstance(fact, list) else [fact]:
                if "when" in alternative:
                    validate_condition(alternative["when"])
    for path in sorted((root / "profiles").glob("*.conf")):
        load_repository(root, profile=path.stem)
