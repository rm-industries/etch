"""Exclusive publication of a fully retrieved and validated consumer module."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from .git import Git
from .report import inventory, validate_module
from .source import parse
from .tree import entries, materialize


def destination(root: Path, name: str) -> Path:
    if not root.is_dir():
        raise ValueError("consumer repository must be an existing directory")
    modules = root / "modules"
    if modules.is_symlink() or (modules.exists() and not modules.is_dir()):
        raise ValueError("consumer modules parent must be a real directory")
    target = modules / name
    if target.exists() or target.is_symlink():
        raise ValueError(
            "import destination already exists: {}; inspect/remove it explicitly before retrying (it may be an incomplete import)".format(
                target
            )
        )
    return target


def publish(staged: Path, target: Path) -> None:
    target.parent.mkdir(exist_ok=True)
    target.mkdir()  # Exclusive reservation: never replace an existing directory.
    try:
        for source in staged.iterdir():
            if source.name != "module.conf":
                shutil.move(str(source), str(target / source.name))
        with tempfile.NamedTemporaryFile(
            dir=target, prefix=".module-conf-", delete=False
        ) as configuration:
            pending = Path(configuration.name)
        shutil.copy2(staged / "module.conf", pending)
        os.replace(pending, target / "module.conf")
    except BaseException:
        shutil.rmtree(target)
        raise


def import_module(
    root: Path, source: str, path: str, ref: str = "HEAD", *, provenance: bool = True
) -> str:
    spec = parse(source, ref, path)
    absolute = root.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValueError("consumer destination parent components must not be symlinks")
    root = root.resolve()
    destination(root, spec.name)
    with tempfile.TemporaryDirectory(prefix="etch-import-") as temporary:
        workspace = Path(temporary)
        git_root = workspace / "objects"
        git_root.mkdir()
        git = Git(git_root)
        commit = git.fetch(spec)
        selected = entries(git, commit, spec.path)
        staging = workspace / "consumer"
        staged = staging / "modules" / spec.name
        staged.mkdir(parents=True)
        materialize(git, selected, staged)
        try:
            module = validate_module(staging, spec.name)
        except (ValueError, OSError, UnicodeError) as exc:
            raise ValueError(
                "module.conf failed structural validation; review its literal syntax, schema, identity, condition and metadata fields"
            ) from exc
        lines = [
            "Source: {!r}".format(spec.url),
            "Requested ref: {!r}".format(spec.ref),
            "Resolved commit: " + commit,
            "Source path: {!r}".format(spec.path),
        ]
        lines.extend(inventory(module, root, selected))
        if git.filter_fallback:
            lines.append(
                "Server did not support blob filtering; acquisition transferred additional objects."
            )
        if provenance:
            metadata = dict(
                schema_version=1,
                source=spec.url,
                requested_ref=spec.ref,
                resolved_commit=commit,
                source_path=spec.path,
            )
            (staged / ".etch-import.json").write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )
            (staged / ".etch-import.json").chmod(0o644)
        target = destination(root, spec.name)
        publish(staged, target)
        lines.append(
            "Imported module into {!r}. Consumer-owned files; no automatic updates or plugin installation.".format(
                str(target)
            )
        )
        return "\n".join(lines)
