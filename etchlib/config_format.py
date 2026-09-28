"""Canonical, dependency-free formatting for module and profile literals."""

import ast
import io
import os
import tempfile
import tokenize
from pathlib import Path
from typing import Iterator, Optional, Sequence

from etchlib.config import ConfigError, read_config


def _position(node: ast.expr, end: bool = False) -> tuple[int, int]:
    if end:
        assert node.end_lineno is not None and node.end_col_offset is not None
        return node.end_lineno, node.end_col_offset
    return node.lineno, node.col_offset


class _Comments:
    def __init__(self, source: str, path: Path) -> None:
        self.path = path
        self.items: list[tuple[tuple[int, int], str]] = []
        self.used: set[int] = set()
        lines = source.splitlines(keepends=True)
        try:
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT:
                    line, column = token.start
                    self.items.append(
                        (
                            (line, len(lines[line - 1][:column].encode("utf-8"))),
                            token.string,
                        )
                    )
        except (tokenize.TokenError, IndentationError) as exc:
            raise ConfigError("{}: {}".format(path, exc)) from exc

    def between(self, start: tuple[int, int], end: tuple[int, int]) -> Iterator[str]:
        for index, (position, text) in enumerate(self.items):
            if index not in self.used and start < position < end:
                self.used.add(index)
                yield text

    def on_line_after(
        self, end: tuple[int, int], limit: tuple[int, int]
    ) -> Optional[str]:
        for index, (position, text) in enumerate(self.items):
            if (
                index not in self.used
                and position[0] == end[0]
                and end < position < limit
            ):
                self.used.add(index)
                return text
        return None


def _render(node: ast.AST, depth: int, width: int, comments: _Comments) -> str:
    if isinstance(node, ast.List):
        inline = (
            "[{}]".format(", ".join(repr(ast.literal_eval(item)) for item in node.elts))
            if all(isinstance(item, (ast.Constant, ast.UnaryOp)) for item in node.elts)
            else ""
        )
        has_comments = any(
            _position(node) < position < _position(node, end=True)
            for position, _ in comments.items
        )
        if inline and not has_comments and width + len(inline) <= 120:
            return inline
    if not isinstance(node, (ast.Dict, ast.List)):
        return repr(ast.literal_eval(node))
    if isinstance(node, ast.Dict):
        entries = list(zip(node.keys, node.values))
        opening, closing = "{", "}"
    else:
        entries = [(None, item) for item in node.elts]
        opening, closing = "[", "]"
    if not entries:
        return opening + closing
    lines = [opening]
    previous = _position(node)
    for index, (key, value) in enumerate(entries):
        start = _position(key if key is not None else value)
        lines.extend(
            "  " * (depth + 1) + text for text in comments.between(previous, start)
        )
        prefix = "  " * (depth + 1)
        if key is not None:
            prefix += repr(ast.literal_eval(key)) + ": "
        rendered = _render(value, depth + 1, len(prefix), comments)
        item_lines = (prefix + rendered + ",").splitlines()
        next_start = (
            _position(entries[index + 1][0] or entries[index + 1][1])
            if index + 1 < len(entries)
            else _position(node, end=True)
        )
        suffix = comments.on_line_after(_position(value, end=True), next_start)
        if suffix is not None:
            item_lines[-1] += "  " + suffix
        lines.extend(item_lines)
        previous = _position(value, end=True)
    lines.extend(
        "  " * (depth + 1) + text
        for text in comments.between(previous, _position(node, end=True))
    )
    lines.append("  " * depth + closing)
    return "\n".join(lines)


def _formatted(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        raise ConfigError("{}: refusing to format a symlink".format(path))
    value = read_config(path)
    original = path.read_text(encoding="utf-8")
    comments = _Comments(original, path)
    tree = ast.parse(original, filename=str(path), mode="eval")
    body = tree.body
    header = list(comments.between((0, 0), _position(body)))
    formatted = "\n".join(header + [_render(body, 0, 0, comments)])
    footer = list(comments.between(_position(body, end=True), (10**9, 0)))
    if footer:
        formatted += "\n" + "\n".join(footer)
    if len(comments.used) != len(comments.items):
        raise ConfigError("{}: cannot safely place all comments".format(path))
    formatted += "\n"
    if ast.literal_eval(formatted) != value:
        raise ConfigError(
            "{}: formatting would change configuration values".format(path)
        )
    return original, formatted


def format_repository(
    root: Path, *, check: bool = False, files: Sequence[Path] = ()
) -> list[Path]:
    """Preflight all files before changing any; return paths needing formatting."""
    if not root.is_dir():
        raise ConfigError("{}: repository directory does not exist".format(root))
    root = root.resolve()
    if files:
        paths = []
        for file in files:
            path = file if file.is_absolute() else root / file
            try:
                relative = path.relative_to(root)
            except ValueError as exc:
                raise ConfigError(
                    "{}: file must be inside {}".format(path, root)
                ) from exc
            if not (
                len(relative.parts) == 3
                and relative.parts[0] == "modules"
                and relative.name == "module.conf"
                or len(relative.parts) == 2
                and relative.parts[0] == "profiles"
                and relative.suffix == ".conf"
            ):
                raise ConfigError(
                    "{}: expected a module or profile configuration".format(path)
                )
            if not path.is_file():
                raise ConfigError("{}: configuration file does not exist".format(path))
            paths.append(path)
    else:
        paths = sorted((root / "modules").glob("*/module.conf")) + sorted(
            (root / "profiles").glob("*.conf")
        )
    changes = []
    for path in paths:
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ConfigError(
                "{}: file resolves outside {}".format(path, root)
            ) from exc
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
