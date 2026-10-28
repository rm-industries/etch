# npm global tools and shared native command support

Implement #163 as an explicitly loaded `plugins/npm` bundle. Install only missing
registry package names, including scoped names, globally; preserve existing
versions and extras. No project operations, arbitrary flags, sudo or bootstrap.

## Approaches

The user selected a shared native-command helper used by npm now over another
standalone runner. Migrating Codex/Homebrew is a future follow-up. Avoid a generic
reconciliation framework: tool identities and installation policies differ.

## Design

`etchlib/providers/native.py` owns lookup and checked argv execution with explicit
cwd/environment, closed stdin, timeouts and streaming output caps. Reject batch
wrappers on Windows; npm.cmd support needs a separate native Node implementation.
The npm bundle owns schema, JSON parsing, flags, facts and reconciliation.

Accept packages, command, timeout and optional prefix. Resolve the effective global
prefix through npm; display and pin it, rejecting executable/prefix drift at apply.
Inherit PATH/npm configuration without initializing version managers. Relative
prefixes resolve from the owning module. Facts expose command/version/packages.

Cache immutable inventories/target resolution only in Context.inspection_cache,
keyed by executable, prefix, cwd, timeout and child environment. Empty requests
launch no native commands. Apply bypasses cached inventory, rechecks the target,
batches missing names and verifies fresh inventory. Nonzero/malformed inventory
fails closed. Partial installs are not rolled back; reapply observes current state.
Preserve npm lifecycle-script policy and flag changed plans as opaque executable
work. The engine therefore conservatively reinspects these plans after unrelated
actions, retaining its existing safety rule. No existing provider is migrated.

## Verification

Disposable CLI tests cover validation, registration, facts/refresh, deterministic
plans, installs/idempotence, partial failure, drift, serialization and process
counts. Actual Python children exercise the helper. Run Ruff, mypy, full pytest
and dependency-free checks. No real global packages are installed.

## Review resolutions

Reject archive-shaped names and pass validated missing operands as `name@*` to
force registry resolution and prevent npm's empty-argument project fallback.
Accept native empty-root `resolved` metadata. A missing Unix prefix/lib is known
empty without launching npm ls (which returns ENOENT there); permissions and
other inventory failures remain errors. Stream both native output pipes into
capped buffers and terminate on overflow before the child finishes.
