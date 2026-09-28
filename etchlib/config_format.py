"""Canonical, dependency-free formatting for module and profile literals."""

import io
import os
import tempfile
import tokenize
from pathlib import Path
from typing import Any

from etchlib.config import ConfigError, read_config


def _render(value: Any, depth: int = 0) -> str:
    if isinstance(value, dict):
        if not value:
            return "{}"
        entries = [
            "{}{}: {},".format("  " * (depth + 1), repr(key), _render(item, depth + 1))
            for key, item in value.items()
        ]
        return "{\n" + "\n".join(entries) + "\n" + "  " * depth + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        entries = [
            "{}{},".format("  " * (depth + 1), _render(item, depth + 1))
            for item in value
        ]
        return "[\n" + "\n".join(entries) + "\n" + "  " * depth + "]"
    return repr(value)


def _formatted(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        raise ConfigError("{}: refusing to format a symlink".format(path))
    value = read_config(path)
    original = path.read_text(encoding="utf-8")
    try:
        if any(
            token.type == tokenize.COMMENT
            for token in tokenize.generate_tokens(io.StringIO(original).readline)
        ):
            raise ConfigError(
                "{}: comments need manual formatting to preserve them".format(path)
            )
    except (tokenize.TokenError, IndentationError) as exc:
        raise ConfigError("{}: {}".format(path, exc)) from exc
    return original, _render(value) + "\n"


def format_repository(root: Path, *, check: bool = False) -> list[Path]:
    """Preflight all files before changing any; return paths needing formatting."""
    if not root.is_dir():
        raise ConfigError("{}: repository directory does not exist".format(root))
    paths = sorted((root / "modules").glob("*/module.conf")) + sorted(
        (root / "profiles").glob("*.conf")
    )
    changes = []
    for path in paths:
        original, formatted = _formatted(path)
        if original != formatted:
            changes.append((path, formatted))
    if not check:
        for path, formatted in changes:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    dir=path.parent,
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(formatted)
                os.chmod(temporary, path.stat().st_mode)
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    return [path for path, _ in changes]
