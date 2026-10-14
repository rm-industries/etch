---
title: "Environment facts"
description: "Declare and inspect observations, understand missing values, and refresh changed state."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

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

## Conditional alternatives

One fact name can choose between platform-specific providers or configurations:

```python
"facts": {
  "version": [
    {"when": {"os": "linux"}, "provider": "version", "command": ["/usr/local/bin/tool", "--version"]},
    {"when": {"os": "macos"}, "provider": "version", "command": ["tool", "--version"]},
  ]
}
```

Each alternative needs a `when` condition and an explicit `provider`. Conditions
can use `os`, `distro`, `arch`, `command`, `env`, and `not`; fact conditions are
excluded to avoid a fact depending on itself during selection. Exactly one
alternative must match. None or multiple matches are configuration errors, so
add explicit alternatives for every supported platform. Only the selected
provider is bound, and its probe remains lazy. Conditions and `refresh` continue
to refer to the single fact name. A single provider declaration still works.

## Scope and lifecycle

Declare module facts as `"facts": {"available": {"provider": "command", "config": "git"}}`.
Dictionary provider options sit beside `provider`, as in
`{"provider": "version", "command": ["git", "--version"]}`. For a scalar
provider payload, use `config`; it cannot be mixed with flat options. The names
`provider`, `when` and `config` are reserved at this declaration level. A plugin
whose own options use one of those names can place its complete payload under
`config`, for example `{"provider": "custom", "config": {"provider": "source"}}`.
The former one-key provider declaration is no longer accepted.
Global `os`, `distro` and `arch` are distinct from module-scoped facts. Conditions
and refresh entries use names declared by their own module. A module named
`global` still has its own scope; it does not replace the global platform facts.
Plugin fact providers use the same declaration syntax.

- VALUE holds successful observations. Missing filesystem paths are VALUE(False).
- UNAVAILABLE represents missing commands, unset environment variables and
  unavailable platform properties. Empty environment strings remain values.
- ERROR records unexpected probe failures, invalid configuration or invalid
  provider output, with reasons. Permission failures are not absence.
- STALE represents an explicitly invalidated cached observation.

Plan and apply gather facts lazily and cache observations until explicitly
refreshed. Unused facts remain unobserved. Successful execution invalidates only
its declared refresh targets; even a successful unchanged execution may refresh
facts, while a skipped or failed action does not. The next consumer observes
fresh state. Inline command/environment conditions inspect current state each
time they are evaluated.

`facts` and `doctor` intentionally gather all declared facts in selected modules,
including unused ones. A version probe runs its declared command; choose a
read-only version query. Environment facts can contain secrets, and diagnostics
print their values. Neither a fact nor a version constraint installs software.
Read [conditions](conditions.md), [versions](versions.md) and [diagnostics](diagnostics.md)
for missing-observation, deferral and output behavior.
