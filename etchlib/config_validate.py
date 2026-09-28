"""Static validation for a consumer's modules and profiles."""

from pathlib import Path

from etchlib.conditions.schema import validate as validate_condition
from etchlib.config import fact_provider, load_repository
from etchlib.core import core_registry
from etchlib.plugins.loader import load_plugins
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import validate_action, validate_fact


def validate_repository(root: Path) -> None:
    """Validate declarations without inspecting state or applying actions."""
    repository = load_repository(root)
    registry = load_plugins(
        repository.root, repository.defaults.get("plugins", []), core_registry()
    ).registry
    for module in repository.modules:
        context = Context(
            repository.root,
            module.root,
            module.name,
            {},
            repository.defaults.get("defaults", {}),
        )
        if "when" in module.config:
            validate_condition(module.config["when"])
        for action in module.config.get("actions", []):
            if "when" in action:
                validate_condition(action["when"])
            name = next(iter(set(action) - {"when", "requires", "after", "refresh"}))
            validate_action(registry.action(name), action[name], context)
        for fact in module.config.get("facts", {}).values():
            for alternative in fact if isinstance(fact, list) else [fact]:
                if "when" in alternative:
                    validate_condition(alternative["when"])
                name, options = fact_provider(alternative)
                validate_fact(registry.fact(name), options, context)
    for path in sorted((root / "profiles").glob("*.conf")):
        load_repository(root, profile=path.stem)
