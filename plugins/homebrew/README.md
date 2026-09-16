# Homebrew reference plugin

This source bundle registers `brew`, plus `brew.command`, `brew.version`,
`brew.formulae`, and `brew.casks` facts. Core does not register it automatically.
It uses Python 3.9+ and the standard library, with no Python package installation.

## Distribution and configuration

Copy this directory to the consumer's `vendor/etch-homebrew`, or reference
`vendor/etch/plugins/homebrew` inside a vendored engine checkout. Declare the path
explicitly in `defaults.conf`:

```python
{
    "schema_version": 1,
    "plugins": ["vendor/etch-homebrew"],
    "defaults": {"brew": {"command": "brew", "timeout": 600}},
}
```

The entrypoint reports bundle name `etch-homebrew`, release `0.1.0`, and plugin API
1. Bundle releases and API compatibility are independent from Etch's release.
`etch plan --verbose` identifies the external provider origin. The initial
[repository decision](../../docs/decisions/0001-foundation.md) keeps reference
bundles in `plugins/` while allowing consumers to vendor each bundle independently.

Example module:

```python
{
    "schema_version": 1,
    "name": "tools",
    "facts": {
        "git_command": {"command": "git"},
        "git_version": {"version": {"command": ["git", "--version"]}},
        "packages": {"brew.formulae": {}},
    },
    "actions": [
        {
            "brew": {
                "formulae": ["git", "tmux", "starship"],
                "casks": ["visual-studio-code"],
            },
            "refresh": ["git_command", "git_version", "packages"],
        },
    ],
}
```

Install Homebrew and expose its CLI first; this provider does not bootstrap it.
Casks require a Homebrew/platform combination that supports them. A formula-only
request never probes casks. CLI lookup follows PATH or accepts an explicit absolute
or module-relative executable path. It never evaluates a shell command string.

`formulae` and `casks` are lists; at least one field is required. Empty lists request
no changes. `command` and `timeout` are the only optional fields and the only action
defaults. Timeout is a positive finite number of seconds per CLI invocation, default
600. Unknown options, including upgrade/removal flags, are rejected.

## Presence and batching policy

The provider inspects requested package types using `brew list --formula` or
`--cask`, with full names and one item per line. Names are trimmed, lowercased,
deduplicated and sorted. The initial syntax supports simple tokens (including
versioned formula names such as `python@3.13`) and `owner/tap/token` names. URLs,
local Ruby/JSON files, arbitrary install flags and alias resolution are unsupported.

Official `homebrew/core/` formula and `homebrew/cask/` cask prefixes normalize to
short names. External tap prefixes are retained: `vendor/tap/git` does not satisfy
a request for core `git`. Formula and cask namespaces remain separate.

Planning installs only missing packages. Application rechecks each type immediately
before installing, batches sorted missing formulae into one `brew install --formula`
call, then does the same for casks. It verifies the requested inventory after each
batch. A dependency installed by earlier work is observed and skipped on replanning.
An exit-zero install that leaves requested packages absent is a failure.

This is presence reconciliation, not version management. Existing packages are not
passed to install, unlisted packages are preserved, and no `upgrade`, `reinstall`,
`uninstall`, `update` or `cleanup` commands are issued. Child environments set:

- `HOMEBREW_NO_INSTALL_UPGRADE=1`
- `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1`
- `HOMEBREW_NO_AUTO_UPDATE=1`
- `HOMEBREW_NO_INSTALL_CLEANUP=1`

These controls suppress implicit install upgrades, dependent checks, auto-update,
and cleanup; they do not prevent Homebrew from resolving required dependencies of
new packages. Required dependency changes remain Homebrew's responsibility, so
this is not a promise to freeze the entire dependency graph. See the official
[Homebrew manual](https://docs.brew.sh/Manpage) and
[version guidance](https://docs.brew.sh/Versions) for those controls and their limits.
The parent process environment is unchanged.

Failure stops later batches without retry or rollback. An earlier successful batch,
or a partial failed batch, may have changed the machine. A subsequent apply observes
that inventory and only requests packages still absent. Homebrew may need platform
permissions for some casks; Etch neither wraps the entire command in sudo nor provides
interactive stdin. Packages requiring unsupported interaction fail explicitly.

## Resources, facts, and refresh

Every action declares `package-manager:brew`. Its default capacity of one serializes
Homebrew mutations across modules, without Homebrew branches in the executor. Keep
that capacity at one. Other independent actions may run concurrently.

`brew.command` returns the resolved executable without invoking it. `brew.version`
runs `--version` using Etch's numeric version parser. Inventory facts return sorted,
normalized name lists. Missing/non-executable Homebrew yields `UNAVAILABLE` facts;
failed probes and invalid output become errors. Fact options are `command` and
`timeout` with the same built-in defaults; fact configurations do not inherit action
defaults. Use the same target for corresponding action and inventory facts.

Action-level `refresh` explicitly names declared observations affected by installation,
including core command/version facts. No program-to-package guessing is performed.
After successful execution Etch marks those facts stale and gathers them on demand,
allowing deferred version-dependent configuration to activate in the same apply.
A failed action does not refresh or release dependent work. Reapplying starts with
fresh observations. Package-manager changes do not rewrite the parent PATH.

Subprocesses use argv, module cwd, closed stdin, per-call timeouts and bounded output
reads (1 MiB per stream). Planning only performs inventory inspection. The bundle
keeps no mutable provider state and changes no process-wide cwd or environment.

## Verification

The suite loads a copied bundle with the real plugin loader and uses an executable
fake CLI. It covers absence, normalized inventories, batches, preserved packages,
upgrade-suppression environment, failed installs, command/version refresh, dependencies,
second-run skips, and resource serialization while unrelated work progresses.
No tests invoke real Homebrew, install packages, or access the network. Ruff, strict
mypy, and the Python 3.9–3.14 Linux/macOS matrix include this bundle.
