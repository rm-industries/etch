"""Standalone bootstrap proof; run with the base interpreter and -I -S."""

import ast
import importlib
import importlib.util
import sys
import sysconfig
from pathlib import Path


def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def check_imports(source: Path) -> None:
    paths = sysconfig.get_paths()
    libraries = [Path(paths[key]).resolve() for key in ("stdlib", "platstdlib")]
    packages = [Path(paths[key]).resolve() for key in ("purelib", "platlib")]
    files = sorted((source / "etchlib").rglob("*.py")) + [source / "etch"]
    for file in files:
        tree = ast.parse(file.read_text(), filename=str(file), feature_version=(3, 9))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                spec = importlib.util.find_spec(root)
                if spec is not None:
                    if spec.origin in ("built-in", "frozen"):
                        continue
                    if spec.origin is not None:
                        origin = Path(spec.origin).resolve()
                        if root == "etchlib" and within(origin, source / "etchlib"):
                            continue
                        if any(
                            within(origin, library) for library in libraries
                        ) and not any(within(origin, package) for package in packages):
                            continue
                raise RuntimeError(
                    "{}:{}: non-standard-library core import: {}".format(
                        file.relative_to(source), node.lineno, name
                    )
                )
    # Import even modules not reached by CLI startup on this interpreter.
    for file in files:
        if file.name == "etch":
            continue
        parts = list(file.relative_to(source).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        importlib.import_module(".".join(parts))


def exercise_core(consumer: Path) -> None:
    # These imports must resolve only after main installs the vendored source path.
    from etchlib.core import core_registry
    from etchlib.providers.contracts import Context
    from etchlib.providers.lifecycle import plan_action
    from etchlib.providers.plans import ApplyResult, PlanStatus

    registry = core_registry()
    context = Context(consumer, consumer / "modules/git", "git", {})
    target = consumer / "runtime-proof" / "nested"
    entry = registry.action("create")
    plan = plan_action(entry, [str(target)], context)
    assert plan.status is PlanStatus.CHANGE
    assert not target.exists(), "planning must not mutate the filesystem"
    result = entry.provider.apply(plan, context)
    assert isinstance(result, ApplyResult) and result.changed
    assert target.is_dir()
    assert plan_action(entry, [str(target)], context).status is PlanStatus.SKIP


def main() -> None:
    assert sys.flags.isolated and sys.flags.no_site
    assert sys.prefix == sys.base_prefix, "bootstrap must not require a virtualenv"
    assert "site" not in sys.modules
    consumer = Path(sys.argv[1]).resolve()
    source = consumer / "vendor" / "etch"
    sys.path.insert(0, str(source))
    check_imports(source)
    import etchlib

    assert etchlib.__file__ is not None
    assert Path(etchlib.__file__).resolve() == source / "etchlib/__init__.py"
    exercise_core(consumer)
    print("Runtime compatibility OK")


if __name__ == "__main__":
    main()
