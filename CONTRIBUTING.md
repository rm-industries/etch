# Contributing to Etch

Start with the [development guide](docs/development.md) for environment setup,
supported Python versions, local checks and bootstrap verification. Etch runs
directly from a checkout; installing Etch as a package is unnecessary.

## Making a change

Choose an issue from the [implementation roadmap](https://github.com/rm-industries/etch/issues/2)
and keep the pull request focused on its acceptance criteria. Keep code in small
files with clear responsibilities and descriptive names. Add or update tests when
behavior changes, and update the relevant documentation alongside the change.

Runtime code must remain compatible with Python 3.9 and use only the standard
library. Development tools are separate dependencies. New annotations must work
on Python 3.9 without importing development-only typing packages.

Before opening a pull request, run the [local quality checks](docs/development.md#local-checks)
and [runtime isolation checks](docs/development.md#runtime-isolation). Describe the
problem, resulting behavior and validation in the pull request, and link its issue.
CI is authoritative: all formatting, linting, typing and test jobs must pass.

## Optional Git hooks

Pre-commit is optional and is not included in the current toolchain. No setup
command installs Git hooks. You may use personal hooks for local feedback, but
running, testing and contributing to Etch must remain possible without them.
Hooks never replace the CI checks.
