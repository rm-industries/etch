---
title: User guide
description: Build a consumer repository, inspect changes, and apply modules safely.
publishedAt: 2026-09-23T12:00:00Z
tags:
  - Etch
  - Guide
draft: false
---

Etch reads configuration from your consumer repository. Start from the
[template](https://github.com/rm-industries/etch-template), clone your copy with submodules, and edit its modules and
profiles. Python 3.9 or newer is required. The engine is pinned by the consumer; updating that pin is a deliberate
repository change.

## Compose a module

Each `modules/<name>/module.conf` is literal configuration data, not Python code. Keep assets beside it. A minimal Git
module looks like this:

```python
{
    "schema_version": 1,
    "name": "git",
    "actions": [
        {"link": {"~/.gitconfig": "files/gitconfig"}},
    ],
}
```

The source `files/gitconfig` belongs in `modules/git/`. The link destination is in the user's home directory. A profile
under `profiles/developer.conf` selects it:

```python
{"schema_version": 1, "name": "developer", "modules": ["git"]}
```

Use `defaults.conf` for repository-wide provider defaults and execution settings. Action options replace nested defaults
rather than merging them. Keep each module focused on one capability, and declare `requires` for a hard module
dependency or `after` for optional ordering. Neither setting downloads or selects a missing module automatically.

## Inspect, then apply

From the consumer repository:

```sh
./etch plan --profile developer
./etch doctor --profile developer
./etch apply --profile developer
```

Bare `./etch` displays the developer plan; it does not apply it. `plan` reports proposed work, skips, conflicts,
required privileges, and opaque command effects without running actions or downloading installers. `doctor` validates
configuration, plugins, declarations, observations, and the active plan; a future condition can remain deferred. Fact
probes and trusted plugin code may run during inspection. `apply` rechecks current state before acting and stops
dispatching new work after a failure. Earlier side effects are not rolled back. Run `./etch facts --profile developer`
to inspect observed platform and module facts; avoid sharing its output if facts can contain secrets.

Filesystem providers compare desired state and can skip satisfied work. Shell, script, and installer actions are opaque:
without a passing `check`, they run again on the next apply. A check is repeated before execution. Existing conflicting
destinations are refused unless a provider's explicit option authorizes the change. Review your first plan before
applying to a real home directory.

## Add commands and installers deliberately

Use `shell` for a short command and `script` for an executable module-owned file. A command argument list bypasses shell
parsing; a command string runs through `/bin/sh -c`. A script path stays within its module. Both support checks,
timeouts, environment overrides, and explicit interactive or privilege settings. Plans cannot know their arbitrary side
effects. See the [command reference](https://github.com/rm-industries/etch/blob/main/docs/commands.md).

The `installer` provider downloads an HTTPS script to a temporary file, validates the response and optional SHA-256
digest, then executes it. It does not pipe a response into a shell. Specify a `check` if installation should be skipped
when the tool is present. Use a pinned upstream URL and digest when available; custom CA trust uses `tls.ca_file` inside
the module. Disabling TLS verification removes certificate validation. An installer has opaque effects and does not
claim every path it might touch. See the [installer
reference](https://github.com/rm-industries/etch/blob/main/docs/installers.md).

## Select, share, and update modules

`./etch import github:owner/repo --path modules/git` copies one module into the fixed `modules/git/` destination in your
consumer repository. The destination must not already exist. Import does not apply it or bring along the source
repository's profiles or defaults. Use a full commit ID or full branch/tag ref with `--ref` to pin the source, review
the copied files, then run `doctor` and `plan`. Imports are copies, not a package registry or automatic updates. See
[importing](https://github.com/rm-industries/etch/blob/main/docs/importing.md).

For observed versions, declare a version fact and use a condition to choose configuration. Etch does not solve package
dependencies or manage tool upgrades from version constraints. Provider plugins, such as the reference Homebrew and VS
Code plugins, are trusted executable code and must be explicitly declared. See [facts and
providers](/etch/docs/facts-and-providers/) and the [architecture reference](/etch/docs/architecture/).
