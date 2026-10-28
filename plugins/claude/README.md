---
title: "Claude Code native plugin reference"
description: "Register native marketplaces and install missing user plugins with the Claude CLI."
publishedAt: 2026-10-27
tags: [Etch, Reference]
draft: false
---

# Claude Code native plugin reference

This optional bundle registers the `claude` action and `claude.command`,
`claude.version`, `claude.marketplaces`, and `claude.plugins` facts. It requires
Python 3.9+ and an installed Claude Code CLI, with no Python dependencies or
Etch core registration. Bundle `etch-claude` 0.1.0 uses plugin API 1 and the shared
native-command helper. Use an engine revision containing that helper.

The native JSON shapes and commands were verified with Claude Code 2.1.312,
including local marketplace registration, user/project installs, and disabled
user plugins in an isolated temporary home. Install and expose the CLI first;
Etch does not bootstrap it, authenticate, or require a paid subscription.
See the official [plugin command reference](https://code.claude.com/docs/en/plugins/cli-reference).

## Register and select

In the consumer's `defaults.conf`:

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/claude'],
  'defaults': {'claude': {'timeout': 120}},
}
```

A module can declare:

```python
{
  'schema_version': 1,
  'name': 'claude',
  'facts': {
    'installed': {'provider': 'claude.plugins'},
  },
  'actions': [
    {
      'claude': {
        'marketplaces': ['mattpocock/skills'],
        'plugins': ['mattpocock-skills@mattpocock'],
      },
      'refresh': ['installed'],
    },
  ],
}
```

Review `etch plan claude --verbose`, then run `etch apply claude`. The module or
profile selects the action. A marketplace source's repository name can differ
from its registered marketplace name; plugin selectors use the registered name.

`marketplaces` and `plugins` are optional lists. Empty categories launch no native
commands. `command` and `timeout` are the only optional target fields and action
defaults. CLI lookup follows PATH or an explicit absolute/module-relative path;
timeout is positive finite seconds per invocation, default 120. Facts accept the
same target fields but do not inherit action defaults. Windows batch wrappers
are rejected; use a native executable.

Sources support `owner/repo`, credential-free HTTPS Git URLs (other hosts require
`.git`), and explicit local marketplace paths. Local paths expand `~` and resolve
against the owning module. HTTP, SSH, pinned refs, hosted JSON URLs, arbitrary
flags, and project/local installation scope options are unsupported. Plugin
selectors must use `plugin@marketplace`; session, skills-directory, and synced
plugins are outside this provider's scope.

## Presence, scope and safety

Inventory comes from `claude plugin marketplace list --json` and
`claude plugin list --json`. Marketplace facts map registered names to normalized
sources; unsupported existing sources map to `None` and remain untouched. Plugin
facts contain sorted installed user plugin selectors. An installed disabled user
plugin satisfies presence. Project, local, managed, session-only and synced
entries cannot satisfy a requested user install.

**Marketplace scope limitation:** the native marketplace list reports known
sources without their settings declaration scope. Presence therefore means the
source is known to the user's native registry, not proof of a user-settings
declaration. Etch does not guess the missing scope or inspect settings files.
New marketplaces and plugins are always added with explicit `--scope user`.

Apply rechecks the executable and current inventory, adds missing marketplaces
first, then reads plugin inventory after any dependency installs caused by those
additions. It installs only missing user plugins and verifies each addition with
fresh inventory. Existing versions, enabled/disabled states, extras, and project
files are preserved. Etch never edits application settings directly or requests
update, removal or cache-cleanup commands. Native dependencies and install side effects remain Claude's own
responsibility. A false-success result or malformed inventory fails explicitly.
Partial success remains installed; fix the error and reapply to install the rest.

Validated inventory is cached only within one planning snapshot, keyed by the
executable, timeout, working directory and user/configuration/cache environment.
Fact values are detached copies. Apply bypasses those caches. Mutations serialize
with `application:claude` within one Etch invocation; external processes are not
locked. Changed plans advertise network access and opaque executable side effects,
so the engine retains its conservative reinspection after unrelated actions.

Native installs can run dependency commands or require trust confirmation. Etch
closes stdin and does not pass `--yes` or accept displayed commands automatically;
trust failures without an interactive terminal remain actionable errors. Review the marketplace
and perform any required native confirmation yourself before reapplying.
