---
title: "npm global tools reference plugin"
description: "Install missing global registry packages without upgrading existing tools."
publishedAt: 2026-10-27
tags: [Etch, Reference]
draft: false
---

# npm global tools reference plugin

This optional Python 3.9+ source bundle registers the `npm` action and
`npm.command`, `npm.version`, and `npm.packages` facts. Bundle `etch-npm` 0.1.0
uses plugin API 1 and the engine's shared native-command helper. It adds no Python
dependencies and is never registered automatically.

Install Node.js and npm first. This provider uses npm's global CLI on Linux/macOS;
its native commands were checked with npm 11.19.1. It does not install npm, select
Node versions, initialize nvm, edit shell files or use sudo. Windows `npm.cmd`
wrappers are rejected: supporting Windows needs an explicit Node/CLI entrypoint
rather than shell interpolation.

## Register and declare tools

In the consumer's `defaults.conf`, declare the bundle explicitly:

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/npm'],
  'defaults': {'npm': {'timeout': 600}},
}
```

You may also copy this directory to `vendor/etch-npm` and register that path, using
an engine revision containing the shared native-command helper.

For example, `modules/npm-tools/module.conf`:

```python
{
  'schema_version': 1,
  'name': 'npm-tools',
  'facts': {
    'packages': {'provider': 'npm.packages'},
    'tldr_command': {'provider': 'command', 'config': 'tldr'},
  },
  'actions': [
    {
      'npm': {'packages': ['tldr']},
      'refresh': ['packages', 'tldr_command'],
    },
  ],
}
```

Run `etch plan npm-tools --verbose`, review the executable, prefix and missing
names, then `etch apply npm-tools`. A second apply is unchanged. Installing a
package does not prove its executable works; a refreshed `command` fact can check
whether your PATH exposes it.

## Options and target selection

| Option | Behavior |
| --- | --- |
| `packages` | Required list of registry names; an empty list launches no native commands |
| `command` | One executable, default `npm`; PATH, absolute and module-relative paths are supported |
| `timeout` | Positive finite seconds per invocation, default `600` |
| `prefix` | Optional global installation directory; `~` expands and relative paths use the module directory |

Only `command`, `timeout`, and `prefix` can be action defaults. Facts accept these
same target options but do not inherit action defaults: repeat a custom target
in facts that should observe it.

Without `prefix`, `npm prefix --global` selects the destination using the effective
npm executable and its inherited user/global npm configuration and environment.
An nvm installation uses the environment already active when Etch starts. Etch
does not source nvm or switch versions. An explicit `command` selects the npm
launcher; its Node runtime still follows the launcher's own behavior and PATH.

Etch pins the resolved absolute prefix with `--prefix` for inventory and installs.
Apply checks the executable, inherited environment fingerprint and current prefix
again. A change fails before installation; run a new plan in the intended
environment. The cache fingerprint does not expose environment values.

Choose a writable user prefix or an existing user-managed Node installation.
For example, `prefix: '~/.local'` puts Unix executables in `~/.local/bin`; ensure
that directory is on PATH before Etch starts. A default prefix such as `/usr/local`
may require permissions the current user lacks. Errors remain explicit; Etch does
not retry with sudo or silently choose another prefix. With nvm, normally omit
`prefix` and use the active version's own global installation.

See npm's [folders](https://docs.npmjs.com/cli/v11/configuring-npm/folders/),
[prefix command](https://docs.npmjs.com/cli/v11/commands/npm-prefix/), and
[configuration](https://docs.npmjs.com/cli/v11/using-npm/config/) references.

## Presence, inventory and failures

Names are lowercase registry names, optionally `@scope/name`, deduplicated and
sorted. Versions, tags, aliases, URLs, Git refs, local paths, archive-shaped names
(`.tar`, `.tar.gz`, `.tgz`), arbitrary flags and upgrade/removal options are rejected.
Presence satisfies a declaration regardless of installed version; existing names are never passed to install.

Inventory uses `npm ls --global --depth=0 --json` for the pinned prefix. Lock-only
and link-only filtering and long output are explicitly disabled. Validated names are cached as an
immutable tuple within one planning snapshot, shared by requests for the same
executable, prefix, timeout, working directory and inherited environment. Empty
requests perform executable lookup but do not query a prefix or inventory.

A fresh Unix prefix without a `lib` directory has no global inventory yet;
Etch treats that missing directory as empty without creating it during planning.
Other filesystem or npm errors remain failures.

Apply bypasses planning caches and rechecks inventory before batching missing
packages into one `npm install --global` invocation. Validated names are passed
internally as `name@*` to force registry interpretation, including when a name
matches the prefix directory. This does not add version selection to declarations. It verifies all requested
names with fresh inventory afterward. Nonzero status, invalid JSON, invalid
entries and reported dependency problems fail closed, even if some names appear
in the output. An empty valid inventory is supported. Disabled/filtered npm
configuration that causes an invalid result must be corrected before applying.

No local install, project manifest or lockfile operation is issued. Install flags
disable audit/funding output, package-lock writes and save operations, and ensure
an inherited dry-run or lock-only setting cannot substitute for installation.
Manually installed extras and existing versions remain untouched. npm still owns
dependency resolution and executable-link conflicts for newly requested packages;
Etch does not freeze the dependency graph or sandbox npm.

Failures stop without automatic retries or rollback. npm may have installed part
of a failed batch. Fix the reported problem and reapply: current inventory decides
which names still need installation. An exit-zero install leaving packages absent
also fails verification.

## Lifecycle scripts and scheduling

Installing a package can execute its lifecycle scripts with your account's access.
Etch preserves npm's configured script policy, including `ignore-scripts` if you
set it; it does not force script execution or suppress scripts needed by a CLI.
Review the requested packages and npm configuration before applying. See npm's
[installation and script policy](https://docs.npmjs.com/cli/v11/commands/npm-install/).

Changed plans advertise network access, possible lifecycle execution and opaque
side effects. The `package-manager:npm` resource serializes npm mutations within
one Etch invocation. It cannot lock out another Etch process or external npm.

Although apply carries stable package intent and reconciles fresh state, the
engine conservatively reinspects opaque plans after other actions. This preserves
existing safety semantics; snapshot caching still deduplicates repeated reads.
No cache survives snapshots or mutations, and no engine rule is bypassed to save
native calls.
