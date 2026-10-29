---
title: "WinGet reference plugin"
description: "Install missing Windows packages by exact ID without upgrading existing applications."
publishedAt: 2026-10-28
tags: [Etch, Reference]
draft: false
---

# WinGet reference plugin

This optional Python 3.9+ source bundle registers the `winget` action and
`winget.command`, `winget.version`, and `winget.packages` facts. Bundle
`etch-winget` 0.1.0 uses plugin API 1, the shared native-command helper and only
the standard library. It is never registered automatically.

Install Windows App Installer and expose `winget.exe` on PATH first. Etch does
not install WinGet, register sources, switch accounts or change PATH. Use a
WinGet release supporting `export --source`, `--disable-interactivity` and
`install --no-upgrade`. Native Windows execution has not yet been verified;
tests simulate WinGet at the shared native-command boundary.

## Register and declare packages

In the consumer's `defaults.conf`:

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/winget'],
  'defaults': {'winget': {'timeout': 600}},
}
```

You may instead copy this bundle to `vendor/etch-winget` and register that path.
For example, `modules/windows-tools/module.conf`:

```python
{
  'schema_version': 1,
  'name': 'windows-tools',
  'when': {'os': 'windows'},
  'facts': {
    'packages': {'provider': 'winget.packages'},
    'command': {'provider': 'winget.command'},
    'version': {'provider': 'winget.version'},
  },
  'actions': [
    {
      'winget': {'packages': ['Git.Git', 'Microsoft.PowerShell']},
      'refresh': ['packages', 'command', 'version'],
    },
  ],
}
```

Run `etch plan windows-tools --verbose`, then
`etch apply windows-tools --allow-sudo`. Nonempty requests conservatively declare
potential elevation because package installers may require administrator access.
Etch's existing `--allow-sudo` gate authorizes that possibility on Windows too;
it does not itself elevate WinGet. Windows still controls authentication and UAC.
A second apply leaves existing packages unchanged.

## Options and facts

| Option | Behavior |
| --- | --- |
| `packages` | Required list of exact package IDs; duplicates are removed and IDs sorted |
| `command` | One native executable; default `winget`; absolute and module-relative paths work |
| `timeout` | Positive finite seconds per command; default `600` |
| `source` | One already configured source name, case-insensitive; default `winget` |

Only `command`, `timeout` and `source` accept action defaults. Facts accept these
same target options but do not inherit action defaults; repeat custom targets in
facts. `winget.command` returns the resolved executable, `winget.version` a parsed
version string, and `winget.packages` a sorted list of IDs exported from the
selected source. Missing executables produce UNAVAILABLE facts. Other command or
inventory failures produce ERROR facts through Etch's normal lifecycle handling.

IDs preserve case and accept ASCII letters, digits, dots, underscores, plus signs
and hyphens, starting with a letter or digit. Use the ID returned by WinGet,
including its case: exact queries are case-sensitive. Versions, URLs, paths,
flags, upgrades, removal, source management, architecture and install-scope
selection are unsupported. The plugin treats a matching package in either user
or machine scope as present; it does not relocate existing applications.

## Inventory, installation and failures

Inventory uses `winget export --source NAME --output FILE --disable-interactivity`
and a disposable file, never localized console tables. JSON must contain a valid
`Sources` list and matching source/package records; malformed, oversized, missing
or unreadable exports fail closed. UTF-8 with or without a BOM is supported.
WinGet can omit applications it cannot correlate with the selected source;
exported inventory is not a list of every program on the machine. See Microsoft's
[export documentation](https://learn.microsoft.com/en-us/windows/package-manager/winget/export).

Planning writes only the temporary export and never installs packages. WinGet may
update its own logs or source caches and contact configured sources during export.
Accept required source terms through WinGet before running Etch; inspection does
not automatically accept them. An empty package request launches no commands.
Inventory tuples are shared only within one planning snapshot for the same
executable, source, working directory and timeout; facts return independent lists.

Apply checks the resolved executable again, bypasses snapshot caches and inspects
fresh inventory. It installs missing IDs individually with `--id`, `--exact`,
`--source`, `--no-upgrade`, `--silent`, `--disable-interactivity`,
`--accept-package-agreements` and `--accept-source-agreements`. Applying therefore
accepts package and source terms. Review those terms before applying. WinGet
still owns installer selection, dependencies, configured source definitions and
OS authentication. The plugin does not pass hash-bypass, force or reboot flags.
See Microsoft's [install documentation](https://learn.microsoft.com/en-us/windows/package-manager/winget/install).

After each installation, fresh inventory verifies progress and prevents
reinstalling another requested package already installed as a dependency.
Existing versions and unrelated packages remain untouched. Exit-zero installs
leaving requested IDs absent fail verification. Failures stop without retry or
rollback; earlier installs may persist. Correct the failure and reapply to install
only remaining missing packages. Installer timeouts can leave child processes
running, so check WinGet's state before retrying.

Plans declare `package-manager:winget`, potential elevation, network access and
opaque installer side effects. The resource serializes WinGet mutations within
one Etch invocation; it cannot lock out another Etch process or external WinGet.
No arbitrary installer arguments or automatic Windows restart are requested.
