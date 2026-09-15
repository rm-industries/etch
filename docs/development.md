# Development tooling

Etch runs directly from source with Python 3.9 or newer and the standard library.
Development packages are never required to run Etch. Do not add third-party
imports to the runtime or install Etch as a package to run these checks.

## Setup

From the repository root, create an optional isolated development environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

The pinned Ruff and pytest versions support Python 3.9 through 3.14. pytest stays
on the 8.4 series to retain Python 3.9 support. The requirements file also pins
pytest's dependencies, using markers for interpreter-specific packages. When
updating pins, verify installation and tests on the oldest supported interpreter
as well as the newest. No Git hooks are installed.

## Local checks

Apply formatting and safe lint fixes:

```sh
ruff format .
ruff check --fix .
```

Check without modifying files and run all tests:

```sh
ruff format --check .
ruff check .
pytest
```

Configuration lives in `pyproject.toml`. Ruff targets Python 3.9 and includes the
extensionless `etch` launcher, `etchlib`, and tests. Its initial rules cover import
ordering, syntax and name errors, common style errors, and Bugbear correctness
checks. Add exceptions only for concrete cases at the smallest practical scope.
pytest collects the existing unittest suite, including bootstrap integration tests.

## Runtime isolation

These commands still work without any development packages:

```sh
python3 -S -m unittest discover -v
python3 -S etch --version
python3 -S etch doctor --repo examples/minimal --profile developer
```

Bootstrap tests construct fresh vendored and recursive-submodule consumers and
run Etch with site packages disabled. Git is needed to construct the submodule
test fixture, but is absent from its runtime PATH.

CI currently runs pytest, the isolated unittest suite and source smoke checks on Python
3.9 and 3.14 on Linux and macOS. Independent format/lint/typecheck/test gates and
the full minor-version matrix are tracked in #48; mypy setup is tracked in #46.
