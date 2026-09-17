# Environment facts

Core fact providers and plugin facts share the same registry. Core registrations
precede plugins, preventing shadowing. Use `etch facts` to gather selected declarations and `etch doctor` to include
probe results in repository validation. See [diagnostics](diagnostics.md) for
filtering, output, exit statuses, and probe behavior.

## Providers

| Provider | Configuration | Value |
| --- | --- | --- |
| os | `{}` | Lowercase platform; Darwin becomes macos |
| distro | `{}` | Linux os-release ID, lowercase |
| arch | `{}` | Lowercase machine; amd64 → x86_64, arm64 → aarch64 |
| command | command name or path | True when executable exists |
| command_path | command name or path | Absolute executable path |
| env | environment variable name | String, including empty string |
| path_exists | path | Boolean; follows symlinks |
| file_exists | path | Boolean; regular file after following symlinks |
| directory_exists | path | Boolean; directory after following symlinks |
| version | command argv and optional timeout | Extracted version string |

Command names use process PATH. Explicit relative command paths and filesystem
paths use the module root; paths support `~`. These are observations, not owned
assets: paths may point outside the module. Presence probes execute no commands;
the [version probe](versions.md) explicitly executes its declared argv without a shell.
Distro reads `/etc/os-release`, falling back to
`/usr/lib/os-release` if absent, without shell evaluation.

## Scope and lifecycle

Declare module facts as `"facts": {"available": {"command": "git"}}`.
`repository_facts(repository, registry)` binds global os/distro/arch and selected
module declarations without probing. Local instances use `FactRef("git", "available")`;
globals use `FactRef(None, "os")`, avoiding collisions with real module names.
Plugin providers resolve through the same registry.

- VALUE holds successful observations. Missing filesystem paths are VALUE(False).
- UNAVAILABLE represents missing commands, unset environment variables and
  unavailable platform properties. Empty environment strings remain values.
- ERROR records unexpected probe failures, invalid configuration or invalid
  provider output, with reasons. Permission failures are not absence.
- STALE represents an explicitly invalidated cached observation.

`FactStore.get` gathers lazily and caches values, unavailable observations and errors.
`peek` never probes. `invalidate` marks only a previously observed fact stale;
the next get refreshes it. Unknown references and duplicate declarations fail
explicitly. Unused facts remain unobserved, including unavailable software.

Declarations, returned values and context snapshots are deep-copied to prevent
accidental cache mutation. Plugin values must support deepcopy. Context snapshots
have read-only mappings and fully qualified keys; trusted plugins can inspect
other cached facts, so this is scope correctness rather than access control.

The store is synchronous. Concurrent access, action-driven refresh and fact dependency
graphs are executor work. The [condition evaluator](conditions.md) supports deferral
using explicit earlier-producer evidence. The planner will decide whether
a required unavailable fact has a producer or is an unresolved error. Version
probes are implemented; the facts CLI remains #22. Arbitrary shell/Python gatherers are
not core configuration features; explicitly loaded plugins are executable code.

Platform probes, local probes, core registration, repository binding and scoped
caching live in separate modules under `etchlib/facts/`.
