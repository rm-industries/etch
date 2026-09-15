# Shell and script actions

Use shell for small inline commands and script for executable assets owned by a
module. Both use shared provider validation, plans and application interfaces.

```python
{"shell": [{
    "description": "Prepare application state",
    "command": ["example", "init"],
    "check": {"directory_exists": "~/.example"},
}]}
{"script": {"path": "scripts/setup.sh", "args": ["--yes"]}}
```

Shell accepts one option dictionary or an ordered list. A command string executes
through `/bin/sh -c`; a command argument list bypasses shell parsing. Script accepts
one dictionary with a module-relative `path` and optional `args` list. Its file must
be executable and remain within the module root; interpreters come from its shebang.
Large local workflows belong in script files rather than long command strings.

## Shared options and context

Both providers support description, quiet, stdin, sudo, env, check and timeout.
These options may be provider defaults with entry-level replacement semantics.
Timeout defaults to 300 positive finite seconds. quiet/stdin/sudo default to False;
quiet discards stdout and stderr, while stdin True inherits interactive input.
Without stdin True, commands read from the null device.

Execution uses the module root as cwd and inherits the user environment, followed
by explicit env overrides. Etch then sets ETCH_MODULE_DIR, ETCH_REPO_DIR, ETCH_MODULE,
ETCH_OS, ETCH_DISTRO and ETCH_ARCH. These metadata names cannot be overridden by env.
Unavailable platform metadata is an empty string. env replaces individual inherited
variables; it does not clear the environment.

Checks support one of command, path_exists, file_exists or directory_exists.
Filesystem checks expand `~` and anchor relative paths to the module root. Command
checks use PATH from the action environment. Passing checks skip commands and are
rechecked before application; no arbitrary shell/Python check language is provided.

## Honest plans and privilege

An unsatisfied action plans RUN with opaque side effects; arbitrary commands are
not treated as reconciled declarative state. Without a check, reruns execute again.
Known input requirements produce stdin-interactive and sudo-interactive resource
metadata. Opaque commands may use network resources the provider cannot infer.

sudo True requests elevation in plan metadata but does not authorize it. Application
also requires `Context.elevation_allowed=True`, supplied by the future executor
after authorization and snapshot validation. The runner then prefixes `sudo -E --`
to that command only. Sudo policy controls environment preservation and may reject
the request; errors propagate. Etch never elevates the whole process or defaults to
privilege. The executor must serialize interactive work and supply authorization to
the correct action context. Tests mock elevated execution; they never invoke sudo.

## Failures and scope

Application preflights runnable scripts and elevation requirements, then processes
entries in order. A nonzero exit or timeout raises an error and stops later entries.
Earlier side effects are not rolled back. Checks can allow a second run to skip;
the returned changed flag means a command ran, not that Etch understood its effects.
Rebuild plans after relevant state changes, as with other providers.

Only the launched process is covered by subprocess timeout handling; this is not
process-tree orchestration. Scripts and commands are trusted executable content.
CLI plan/apply and resource scheduling remain separate issues.

Option normalization, runtime context/checks, and provider lifecycle are separated
under `etchlib/providers/commands/`.
