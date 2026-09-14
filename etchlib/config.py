"""Read configuration as data, without importing or executing consumer code."""
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from etchlib import SCHEMA_VERSION


class ConfigError(ValueError):
    """A configuration problem suitable for a user-facing diagnostic."""


def read_config(path: Path) -> Dict[str, Any]:
    try:
        value = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, RecursionError) as exc:
        raise ConfigError("{}: {}".format(path, exc)) from exc
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ConfigError("{}: expected a dictionary with string keys".format(path))
    version = value.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ConfigError("{}: schema_version must be {}".format(path, SCHEMA_VERSION))
    return value


def names(value: Any, path: Path, field: str) -> List[str]:
    if not isinstance(value, list) or any(
        not isinstance(name, str) or not name or name in (".", "..")
        or "/" in name or "\\" in name for name in value
    ):
        raise ConfigError("{}: {} must be a list of simple names".format(path, field))
    if len(set(value)) != len(value):
        raise ConfigError("{}: {} contains duplicate names".format(path, field))
    return value


@dataclass(frozen=True)
class Module:
    name: str
    root: Path
    config: Dict[str, Any]

    def asset(self, value: str) -> Path:
        """Resolve owned assets independently of the invoking process directory."""
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ConfigError("{}: assets must be nonempty module-relative paths".format(self.name))
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ConfigError("{}: asset escapes module root: {}".format(self.name, value)) from exc
        return candidate


@dataclass(frozen=True)
class Repository:
    root: Path
    modules: Tuple[Module, ...]
    defaults: Dict[str, Any]


def load_repository(root: Path, profile: Optional[str] = None,
                    selected: Optional[List[str]] = None) -> Repository:
    root = root.resolve()
    if not root.is_dir():
        raise ConfigError("{}: repository directory does not exist".format(root))
    if profile is not None and selected:
        raise ConfigError("choose either --profile or module names")
    defaults_path = root / "defaults.conf"
    defaults = read_config(defaults_path) if defaults_path.exists() else {"schema_version": SCHEMA_VERSION}
    default_options = defaults.get("defaults", {})
    if not isinstance(default_options, dict) or any(
        not isinstance(key, str) or not isinstance(value, dict)
        for key, value in default_options.items()
    ):
        raise ConfigError("{}: defaults must map provider names to option dictionaries".format(defaults_path))
    paths = sorted((root / "modules").glob("*/module.conf"))
    available = {}
    for path in paths:
        config = read_config(path)
        name = config.get("name")
        names([name], path, "name")
        if name in available:
            raise ConfigError("{}: duplicate module name {!r}".format(path, name))
        if name != path.parent.name:
            raise ConfigError("{}: name must match module directory".format(path))
        actions = config.get("actions", [])
        if not isinstance(actions, list) or any(not isinstance(action, dict) for action in actions):
            raise ConfigError("{}: actions must be a list of dictionaries".format(path))
        for field in ("requires", "after"):
            names(config.get(field, []), path, field)
        if not isinstance(config.get("facts", {}), dict):
            raise ConfigError("{}: facts must be a dictionary".format(path))
        available[name] = Module(name, path.parent, config)
    if profile is not None:
        names([profile], root, "profile")
        path = root / "profiles" / (profile + ".conf")
        config = read_config(path)
        if config.get("name") != profile:
            raise ConfigError("{}: name must match profile filename".format(path))
        chosen = names(config.get("modules"), path, "modules")
    elif selected:
        chosen = names(selected, root, "modules")
    else:
        chosen = list(available)
    missing = [name for name in chosen if name not in available]
    if missing:
        raise ConfigError("{}: missing modules: {}".format(root, ", ".join(missing)))
    if not chosen:
        raise ConfigError("{}: no modules selected or discovered under modules/".format(root))
    return Repository(root, tuple(available[name] for name in chosen), defaults)
