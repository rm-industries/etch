"""Read configuration as data, without importing or executing consumer code."""

import ast
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from etchlib import SCHEMA_VERSION


class ConfigError(ValueError):
    """A configuration problem suitable for a user-facing diagnostic."""


def data_shape(value: Any, path: Path, field: str = "configuration") -> None:
    """Restrict literal syntax to the data types supported by schema 1."""
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ConfigError("{}: {} must use string keys".format(path, field))
        for key, child in value.items():
            data_shape(child, path, field + "." + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            data_shape(child, path, "{}[{}]".format(field, index))
    elif value is not None and type(value) not in (str, bool, int, float):
        raise ConfigError(
            "{}: {} contains unsupported {}".format(path, field, type(value).__name__)
        )


def fields(value: Dict[str, Any], allowed: Tuple[str, ...], path: Path) -> None:
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ConfigError("{}: unknown fields: {}".format(path, ", ".join(unknown)))


def condition(value: Any, path: Path, field: str) -> None:
    if not isinstance(value, dict) or not value:
        raise ConfigError(
            "{}: {} must be a nonempty condition dictionary".format(path, field)
        )


def compose_defaults(
    provider: str,
    defaults: Dict[str, Any],
    options: Dict[str, Any],
    allowed: Tuple[str, ...],
) -> Dict[str, Any]:
    """Provider opt-in composition: replace whole option values, never deep merge.

    Providers supply their allowed default keys and separately validate the result.
    Providers with non-dictionary payloads normalize options before using this helper.
    """
    if not isinstance(defaults, dict) or not isinstance(options, dict):
        raise ConfigError(
            "{}: defaults and options must be dictionaries".format(provider)
        )
    data_shape(defaults, Path(provider), "defaults")
    data_shape(options, Path(provider), "options")
    unknown = sorted(set(defaults) - set(allowed))
    if unknown:
        raise ConfigError(
            "{}: unsupported default options: {}".format(provider, ", ".join(unknown))
        )
    return deepcopy(dict(defaults, **options))


def destination(value: str, repo_root: Path) -> Path:
    """Expand user paths; relative destinations use the consumer repository root.

    Resolve parent directories, but preserve the final component: an existing
    destination symlink is the object being managed, not its current target.
    """
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ConfigError("destination must be a nonempty path without NUL characters")
    try:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = repo_root.resolve() / path
        return path.parent.resolve() / path.name
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfigError("invalid destination {!r}: {}".format(value, exc)) from exc


def read_config(path: Path) -> Dict[str, Any]:
    try:
        tree = ast.parse(
            path.read_text(encoding="utf-8"), filename=str(path), mode="eval"
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                seen = set()
                for key in node.keys:
                    if not isinstance(key, ast.Constant) or not isinstance(
                        key.value, str
                    ):
                        raise ConfigError(
                            "{}: line {}: dictionary keys must be strings".format(
                                path, node.lineno
                            )
                        )
                    if key.value in seen:
                        raise ConfigError(
                            "{}: line {}: duplicate key {!r}".format(
                                path, key.lineno, key.value
                            )
                        )
                    seen.add(key.value)
        value = ast.literal_eval(tree)
        data_shape(value, path)
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        ValueError,
        TypeError,
        RecursionError,
    ) as exc:
        raise ConfigError("{}: {}".format(path, exc)) from exc
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ConfigError("{}: expected a dictionary with string keys".format(path))
    version = value.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ConfigError("{}: schema_version must be {}".format(path, SCHEMA_VERSION))
    return value


def names(value: Any, path: Path, field: str) -> List[str]:
    if not isinstance(value, list) or any(
        not isinstance(name, str)
        or not name.strip()
        or "\x00" in name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        for name in value
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
        if (
            not isinstance(value, str)
            or not value
            or "\x00" in value
            or Path(value).is_absolute()
        ):
            raise ConfigError(
                "{}: assets must be nonempty module-relative paths".format(self.name)
            )
        try:
            candidate = (self.root / value).resolve()
            candidate.relative_to(self.root.resolve())
        except (ValueError, OSError, RuntimeError) as exc:
            raise ConfigError(
                "{}: asset escapes module root: {}".format(self.name, value)
            ) from exc
        return candidate


@dataclass(frozen=True)
class Repository:
    root: Path
    modules: Tuple[Module, ...]
    defaults: Dict[str, Any]


def load_repository(
    root: Path, profile: Optional[str] = None, selected: Optional[List[str]] = None
) -> Repository:
    root = root.resolve()
    if not root.is_dir():
        raise ConfigError("{}: repository directory does not exist".format(root))
    if profile is not None and selected:
        raise ConfigError("choose either --profile or module names")
    defaults_path = root / "defaults.conf"
    defaults = (
        read_config(defaults_path)
        if defaults_path.exists()
        else {"schema_version": SCHEMA_VERSION}
    )
    fields(defaults, ("schema_version", "defaults", "plugins"), defaults_path)
    plugins = defaults.get("plugins", [])
    if not isinstance(plugins, list) or any(
        not isinstance(p, str) or not p.strip() or "\x00" in p for p in plugins
    ):
        raise ConfigError(
            "{}: plugins must be a list of nonempty paths".format(defaults_path)
        )
    if len(set(plugins)) != len(plugins):
        raise ConfigError("{}: duplicate plugin paths".format(defaults_path))
    default_options = defaults.get("defaults", {})
    if not isinstance(default_options, dict) or any(
        not isinstance(key, str) or not isinstance(value, dict)
        for key, value in default_options.items()
    ):
        raise ConfigError(
            "{}: defaults must map provider names to option dictionaries".format(
                defaults_path
            )
        )
    names(list(default_options), defaults_path, "default provider names")
    paths = sorted((root / "modules").glob("*/module.conf"))
    available = {}
    for path in paths:
        config = read_config(path)
        fields(
            config,
            ("schema_version", "name", "actions", "facts", "requires", "after", "when"),
            path,
        )
        name = config.get("name")
        names([name], path, "name")
        if name in available:
            raise ConfigError("{}: duplicate module name {!r}".format(path, name))
        if name != path.parent.name:
            raise ConfigError("{}: name must match module directory".format(path))
        actions = config.get("actions", [])
        if not isinstance(actions, list) or any(
            not isinstance(action, dict) for action in actions
        ):
            raise ConfigError("{}: actions must be a list of dictionaries".format(path))
        for index, action in enumerate(actions):
            metadata = ("when", "requires", "after", "refresh")
            providers = set(action) - set(metadata)
            if len(providers) != 1:
                raise ConfigError(
                    "{}: actions[{}] must declare exactly one provider".format(
                        path, index
                    )
                )
            names(list(providers), path, "actions[{}] provider".format(index))
            for field in ("requires", "after", "refresh"):
                names(
                    action.get(field, []), path, "actions[{}].{}".format(index, field)
                )
            if "when" in action:
                condition(action["when"], path, "actions[{}].when".format(index))
        if "when" in config:
            condition(config["when"], path, "when")
        for field in ("requires", "after"):
            names(config.get(field, []), path, field)
        if not isinstance(config.get("facts", {}), dict):
            raise ConfigError("{}: facts must be a dictionary".format(path))
        for fact, declaration in config.get("facts", {}).items():
            names([fact], path, "fact name")
            if not isinstance(declaration, dict) or len(declaration) != 1:
                raise ConfigError(
                    "{}: fact {!r} must declare exactly one provider".format(path, fact)
                )
            names(list(declaration), path, "fact {!r} provider".format(fact))
        available[name] = Module(name, path.parent, config)
    if profile is not None:
        names([profile], root, "profile")
        path = root / "profiles" / (profile + ".conf")
        config = read_config(path)
        fields(config, ("schema_version", "name", "modules"), path)
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
        raise ConfigError(
            "{}: no modules selected or discovered under modules/".format(root)
        )
    return Repository(root, tuple(available[name] for name in chosen), defaults)
