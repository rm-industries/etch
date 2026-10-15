---
title: "Codex native plugin reference"
description: "Register native Codex marketplaces and install missing user plugins without changing existing versions or enabled state."
publishedAt: 2026-10-15
tags: [Etch, Reference]
draft: false
---

# Codex native plugin reference

This optional bundle registers the `codex` action and `codex.command`,
`codex.version`, `codex.marketplaces` and `codex.plugins` facts. It manages
presence through the native CLI, so installation uses the same user plugin
configuration and cache as Codex. It does not create skill links or edit that
configuration directly. Bundle version: `etch-codex` 0.1.0, plugin API 1.

Install Codex first and expose its CLI. The provider requires the native JSON
plugin commands available in Codex CLI 0.154.0; an older CLI without them fails
explicitly. It does not install or upgrade Codex itself. See the official
[marketplace documentation](https://developers.openai.com/plugins/build/plugins)
for marketplace formats and native application behavior.

## Register and select

In the consumer's `defaults.conf`, explicitly load the bundle:

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/codex'],
  'defaults': {'codex': {'timeout': 120}},
}
```

In `modules/codex/module.conf`:

```python
{
  'schema_version': 1,
  'name': 'codex',
  'actions': [
    {
      'codex': {
        'marketplaces': ['mattpocock/skills'],
        'plugins': ['mattpocock-skills@mattpocock'],
      },
    },
  ],
}
```

`marketplaces` contains **sources**, whereas `plugins` contains
`plugin-name@registered-marketplace-name` selectors. A repository named `skills`
can register a marketplace named `mattpocock`; Etch does not guess that name from
the repository. Review the catalog and its actual plugin names before copying
this example. Select this module directly, or include `codex` in a profile:

```sh
etch plan codex
etch apply codex
```

## Options and sources

| Option | Behavior |
| --- | --- |
| `marketplaces` | List of marketplace sources, default empty. Declaration order is retained; duplicates are removed. |
| `plugins` | List of exact `plugin@marketplace` selectors, default empty. Duplicates are removed and installation order is sorted. |
| `command` | One executable, default `codex`; PATH names and absolute or module-relative paths are accepted. |
| `timeout` | Positive finite seconds per CLI call, default 120. This is not a whole-action deadline. |

Only `command` and `timeout` accept action defaults. Explicit action values replace
them. Facts accept the same two target options with their own built-in defaults;
they do not inherit action defaults. Unsupported options fail before invoking Codex. On Windows, select the native
`codex.exe`; batch wrappers (`.cmd` and `.bat`) are rejected to avoid implicit
shell parsing.

Sources can be GitHub `owner/repo`, credential-free HTTPS Git URLs, or explicit
local paths (`./catalog`, `../catalog`, `~/catalog` or an absolute path). Relative
paths anchor to the module. GitHub shorthand and equivalent HTTPS URLs compare as
the same source, independently of the registered marketplace name. Local sources
compare by their resolved path. SSH, ref selectors, sparse checkouts, HTTP,
embedded credentials, URL queries and fragments are not supported declarations.
Existing unsupported sources and extra marketplaces remain untouched; unknown
source metadata cannot satisfy a declared source.

Codex inherits the calling user's environment, including `HOME` and `CODEX_HOME`.
Choose these before starting Etch to target an isolated user environment. Module
selection does not create a different Codex installation scope. Native CLI
configuration and project trust rules still apply. No login, credentials, paid
subscription setup, project-local installation, or authentication flow is performed
by Etch; native policies can reject installation and that error is reported.

## Reconciliation and failures

Plan reads `plugin marketplace list --json` and `plugin list --json`. It does not
add marketplaces or plugins. Only rows in the native **installed** list count;
available catalog entries are not installed plugins. Disabled installed plugins
are satisfied and remain disabled. Existing versions and unlisted entries are
preserved; Etch does not infer an upgrade, removal, or enable/disable operation.

Apply locates the same executable and reads fresh inventory. It adds missing
marketplaces first with `plugin marketplace add SOURCE --json`, verifies their
sources, then installs missing selectors with `plugin add NAME@MARKETPLACE --json`.
A marketplace name already registered from another source is a native error;
Etch does not remove or replace that registration to resolve the conflict.
Each installation is verified by fresh inventory, rather than trusting exit status
or a success message. An exit-zero response with missing state is a failure.

Every action reserves `application:codex`, including alternate executables. Calls
use argument lists, closed stdin, a bounded timeout and a 1 MiB limit per output
stream. CLI errors, invalid JSON, inconsistent installed identities, duplicate
inventory entries and unsupported response shapes fail explicitly. There is no
automatic retry. Successful additions survive a later failure; rerunning apply
reconciles the remaining missing entries. Normal apply failure propagation still
blocks dependent chains and allows independent modules to continue.

The native listing may contact remote services and populate its own discovery
cache even during plan. A native warning on stderr with exit zero is not treated
as a complete remote-directory inventory: this provider uses the explicit local
installed list and registered marketplace sources only. It does not manage remote
service connections or claim to reconcile the universal remote plugin directory.
Restart or refresh the Codex desktop app if it has not yet reloaded a CLI-installed
plugin; Etch does not restart the app or verify a running app's UI.

## Facts and refresh

- `codex.command`: resolved executable path, without launching it.
- `codex.version`: numeric version parsed from `codex --version`.
- `codex.marketplaces`: mapping from registered names to normalized sources;
  built-in or unsupported sources have a null value.
- `codex.plugins`: sorted installed selectors, including disabled plugins.

A missing executable returns `UNAVAILABLE`. CLI and inventory failures become
fact errors. Declare facts only when needed and refresh them after successful
installation if later actions use them:

```python
{
  'schema_version': 1,
  'name': 'codex',
  'facts': {
    'installed_plugins': {
      'provider': 'codex.plugins',
      'config': {'command': 'codex'},
    },
  },
  'actions': [
    {
      'codex': {'plugins': ['mattpocock-skills@mattpocock']},
      'refresh': ['installed_plugins'],
    },
  ],
}
```

Refresh does not discover a marketplace or install a plugin by itself. The example
above assumes that marketplace is already registered. Module dependencies express
ordering; declared refreshes update observations used by conditions.
