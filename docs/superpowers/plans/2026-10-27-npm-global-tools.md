# npm Global Tools Implementation Plan

> Implement inline with superpowers:executing-plans using test-first cycles.

**Goal:** Install missing global npm tools using shared native command support.
**Architecture:** Engine utility for subprocess mechanics; independent npm bundle
for validation, inventory, facts and presence reconciliation. Existing plugins unchanged.
**Tech Stack:** Python 3.9+, standard library, existing unittest/pytest/Ruff/mypy.
**Spec:** `docs/superpowers/specs/2026-10-27-npm-global-tools-design.md`

## Global Constraints

- Standard-library runtime; existing provider APIs and source-bundle registration.
- No project operations, inferred upgrades/removals, sudo or manager bootstrap.
- Snapshot inventory caching only; fresh apply and post-write verification.

## Review Focus

- Executable/prefix/environment drift must not redirect installations.
- Malformed/nonzero inventory must not become an empty inventory.
- Existing and partially installed tools must not be installed again.
- Empty requests launch no commands; snapshot caches remain isolated.
- Child cwd/environment/argv must not mutate parent state or invoke a shell.

### Task 1: Shared helper

Files: `etchlib/providers/native.py`, `tests/test_native_commands.py`.
Interfaces: `locate(command, cwd, env=None) -> Optional[str]`;
`run(executable, args, *, cwd, timeout, label, env=None) -> str`.

- [x] Add failing tests for literal argv, cwd/env/stdin, lookup, nonzero exits,
  timeout/output limits, invalid encoding and batch rejection.
- [x] Implement mechanics; run focused tests, lint and typing.

### Task 2: npm bundle

Files: `plugins/npm/{__init__,schema,cli,action,facts,etch_plugin}.py`,
`tests/npm_fixtures.py`, `tests/fixtures/npm_cli.py`, `tests/test_npm_*.py`.
Interfaces: action `npm` takes packages/command/timeout/optional prefix;
facts `npm.command`, `npm.version`, `npm.packages` take target options.

- [x] Add failing registration/validation/inventory/install/idempotence/drift tests,
  partial failure/reapply, refresh, serialization and snapshot/process-count tests.
- [x] Implement schema and immutable inventory caching, action and facts.
- [x] Run focused tests and resolve failures.

### Task 3: Documentation and verification

Files: `plugins/npm/README.md`, `docs/provider-authoring.md`, `docs/plugins.md`.

- [x] Document registration/example, prerequisites, prefix/PATH/lifecycle policy,
  platform limits and partial failure recovery.
- [x] Run format/lint, strict typing, full pytest, source-only smoke and focused
  dependency-free tests, plus raw `git diff --check`.

## Verification record

- Baseline: 518 tests passed, 10 platform skips.
- Final Python suite: 549 passed, 10 platform skips; Ruff format/lint and strict mypy pass.
- Python 3.9.6 with site packages disabled: all 31 new focused tests pass.
- Real npm 11.19.1 read-only probes: command/version/packages, satisfied plans,
  fresh and empty prefixes, link/lock-only and long-output overrides pass.
- Website: 38 unit tests pass; documentation page builds and validates.
- Independent targeted review has no remaining blocking findings.
- No real global installs, external publication, or existing-provider migration.
