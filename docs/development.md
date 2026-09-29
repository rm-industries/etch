# Development tooling

Etch runs directly from source with Python 3.9 or newer and the standard library.
Development packages are never required to run Etch. Do not add third-party
imports to the runtime or install Etch as a package to run these checks.

| Use | Requirements |
| --- | --- |
| Run Etch | Python 3.9+ and its standard library; no pip installation or virtual environment |
| Develop Etch | Python, pip, Ruff, pytest and mypy; Git for the complete bootstrap test suite |
| Local hooks | Optional personal convenience; pre-commit is not installed or required |

Installer integration tests bind a temporary HTTPS server to loopback. They use
checked-in test-only certificates and never contact or execute public installers.
An environment that blocks local socket binding must allow it to run the full suite.

## Setup

From the repository root, create an optional isolated development environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Use Python 3.14 for development to match CI's quality jobs; Python 3.9–3.14 is
supported by the pinned tools. The commands above use whichever interpreter
`python3` names. Use `python3.14` in the first command if you need to select it
explicitly. Run all commands in this guide from the repository root. Use
`deactivate` when you want to leave the development environment.

The pinned Ruff, pytest and mypy versions run on Python 3.9 through 3.14. pytest stays
on the 8.4 series and mypy on 1.18.2 to retain Python 3.9 support. The requirements
file uses shared pins in `requirements/constraints.txt`, including dependencies and
markers for interpreter-specific packages. CI uses those same constraints to install
only Ruff, mypy or pytest and its dependencies in the corresponding job. When
updating pins, verify installation and tests on the oldest supported interpreter
as well as the newest. No Git hooks are installed.

## Local checks

Apply formatting and safe lint fixes:

```sh
ruff format .
ruff check --fix .
python3 -S etch format --repo examples/minimal
python3 -S etch format --repo examples/developer
```

Check without modifying files and run all tests:

```sh
ruff format --check .
python3 -S etch format --check --repo examples/minimal
python3 -S etch format --check --repo examples/developer
ruff check .
mypy etchlib plugins tests etch
pytest
```

Configuration lives in `pyproject.toml`. Ruff targets Python 3.9 and includes the
extensionless `etch` launcher, `etchlib`, reference plugins, and tests. Its initial
rules cover import ordering, syntax and name errors, common style errors, and Bugbear correctness
checks. Add exceptions only for concrete cases at the smallest practical scope.
pytest collects the existing unittest suite, including bootstrap integration tests.

Etch's `format` command uses a fixed two-space style for module and profile
configuration. Short scalar lists stay inline; longer or nested lists split.
`.editorconfig` offers matching editor hints; it does not configure the formatter.
Comments are preserved when they can be placed safely; unsupported positions
fail clearly without changing files. `etch validate` separately checks module,
profile, condition, and provider declarations without inspecting state or running
actions. It loads declared plugins, which are trusted Python code.

## Static typing

mypy runs in strict mode with `python_version = "3.9"`, regardless of the interpreter
running the tool. Both `mypy` (using the configured file list) and
`mypy etchlib plugins tests etch` check the entire library, reference plugins, tests,
and extensionless launcher.
The separate typecheck CI job uses the explicit command on Python 3.14; tests on
actual supported interpreters independently verify runtime compatibility.

All functions require complete signatures. Strict mode also rejects untyped calls,
bare generics, implicit optional arguments and unchecked `Any` returns, and reports
unused ignores and redundant casts. No modules or tests are excluded. Runtime
annotations use the standard library; `typing_extensions` is a development-only
dependency of mypy and must not be imported by Etch.

Configuration values, provider-owned observation/plan payloads and dynamically
loaded plugin instances deliberately retain `Any`: their shapes belong to provider
validation, not a closed core schema. The lifecycle wrapper validates plugin
results at runtime. Keep that flexibility at those boundaries and use concrete
types for core records, contexts, facts, graphs and return values.

Negative tests intentionally violate record types, frozen fields or plugin
protocols. Each necessary ignore names its error code and explains the tested
violation on that line; normal assertions narrow optional results explicitly.
The refresh-evidence cast records the graph builder's invariant that a refresh
node carries a fact reference. Do not add broad ignores to silence real mistakes.

## Runtime isolation

These commands still work without any development packages:

```sh
python3 -S -m unittest discover -v
python3 -S etch --version
python3 -S etch doctor --repo examples/minimal --profile developer
```

Bootstrap tests construct fresh vendored and recursive-submodule consumers. Their
Python-only runtime PATH points to the base interpreter, even when pytest itself
runs in a development virtual environment. The consumer launcher executes Etch
directly with site packages disabled; no package installation is involved. Git is
needed to construct the submodule fixture, but is absent from its runtime PATH.

Both layouts also run a standalone probe with `-I -S`. It checks that no virtual
environment or site module is active, verifies the loaded Etch source location,
imports every core module, and plans/applies an idempotent directory creation.
The probe inspects import declarations throughout core and the launcher, including
dormant branches, and accepts only vendored Etch or modules from that interpreter's
standard library. Site-package origins are rejected even if a package is importable.
Negative tests prove detection of available and missing third-party imports, missing
standard-library imports, and isolation from an inherited Python search path.
Explicit external plugins remain outside the core import policy and are exercised
through the recursive-clone consumer's normal `doctor` invocation.

Run this coverage directly with either test runner:

```sh
pytest tests/test_bootstrap.py tests/test_runtime_imports.py
python3 -S -m unittest tests.test_bootstrap tests.test_runtime_imports -v
```

This is a compatibility check, not a security sandbox or exhaustive analysis of
dynamic imports. Importing every module catches import-time API incompatibilities;
the runtime suite on each interpreter exercises APIs used inside functions. Keep
the Python 3.9 grammar check and actual Python 3.9 test runs alongside these probes.

## CI quality gates

Every push and pull request runs independent `format`, `lint`, `typecheck` and `test`
jobs. The first three run on Linux with Python 3.14 and use the same non-mutating
commands shown above. Ruff and mypy still target Python 3.9.

| Job | Exact CI check |
| --- | --- |
| `format` | `ruff format --check .` |
| `lint` | `ruff check .` |
| `typecheck` | `python -m mypy etchlib plugins tests etch` |
| `test` | `python -m pytest` |

The module forms above use the active environment's interpreter and are equivalent
to the `mypy` and `pytest` commands in the local workflow. Every test job also runs
all three dependency-free commands in [Runtime isolation](#runtime-isolation).

The test matrix runs Python 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14 on both Linux and
macOS. Every combination runs pytest, the isolated unittest suite and direct-source
version/doctor checks, including the vendored/submodule bootstrap proof. Each test
job installs only pytest and its dependencies. A failing combination does not
cancel the others, so all compatibility failures remain visible.

CI does not apply formatting or lint fixes. A failing quality job must be corrected
locally and checked again before merging. Keep the supported-version list and
workflow matrix in sync when adding support for a new stable Python minor.

`project.yml` also runs weekly to catch Python and operating-system drift. Its
release-candidate job boots a source archive with Python 3.9, site packages
disabled, and no installed Etch package. The template-consumer job applies a
candidate engine to the generic starter on Linux and macOS. Etch owns the deeper
provider, planning, reconciliation, conflict, and resource tests; the
`etch-template` and `rahul0705/dotfiles` repositories test their own consumer
configurations rather than copying this engine matrix. Their consumer workflows
can use the same plan/apply/doctor and second-apply pattern.

Repository automation is separate from engine CI. `automation.yml` runs
actionlint and zizmor for workflow changes and weekly drift. Dependency Review
checks every pull request and fails on high-severity dependency changes. CodeQL
uses GitHub's repository-level default setup for Actions, JavaScript/TypeScript,
and Python, including its managed schedule, instead of a maintained workflow.
That CodeQL setting and the labels live on GitHub, so a new repository must
enable or create them separately; they are not copied with this Git tree.
Dependabot checks GitHub Actions at 05:00 UTC and website npm dependencies at
05:30 UTC each Monday; `dependencies`, `github-actions`, and `npm` are repository
labels. The seven-day cooldown avoids brand-new releases; Actions updates are
grouped, while npm minor and patch updates are grouped by production or
development and majors remain separate. Website-specific formatting, tests,
and publishing remain in `website.yml`.
