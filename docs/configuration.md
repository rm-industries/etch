---
title: "Configuration reference"
description: "Module, profile and defaults syntax, path rules, overrides, ordering and refresh."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Configuration reference

Etch reads literal dictionaries from the consumer. They are data, not executable
Python; use `True`, `False`, strings, numbers, lists and dictionaries. Expressions,
imports, duplicate keys and unsupported schema versions are rejected. There is
no general environment-variable or template interpolation.

## Layout and identity

```text
etch                         # consumer launcher
vendor/etch/                 # pinned engine
modules/git/module.conf
modules/git/files/gitconfig
profiles/developer.conf
defaults.conf
```

`modules/` and `profiles/` are fixed discovery locations. Each module's `name`
matches its directory and a profile's `name` matches its filename stem. Assets
belong inside their module. The launcher and engine location are consumer choices;
`--repo` always selects the consumer root.

## Modules

```python
{
  'schema_version': 1,
  'name': 'git',
  'actions': [
    {'link': {'~/.gitconfig': {'path': 'files/gitconfig', 'create': True}}},
  ],
}
```

A module declares `schema_version`, `name`, and optional `facts`, `actions`,
`when`, `requires` and `after`. Actions are an ordered list. Each action names
exactly one provider and its payload, with optional `when`, `requires`, `after`
and `refresh` metadata beside it. Provider options belong inside the payload.

```python
{
  'schema_version': 1,
  'name': 'tool',
  'facts': {'available': {'provider': 'command', 'config': 'tool'}},
  'actions': [
    {'link': {'~/.config/tool/config': 'files/config'},
     'when': {'fact': {'name': 'available', 'equals': True}}},
  ],
}
```

Module `when` gates the whole module; action `when` gates individual actions.
An unavailable required fact may defer an action only when an eligible earlier
producer can refresh it. See [conditions](conditions.md) and [facts](facts.md).

`requires: ['base']` requires that selected, active module to finish first.
`after: ['optional']` orders after it when selected/active and warns when absent.
Neither adds the other module to selection. Action-level dependencies add ordering
at that action. Cycles are errors. Actions within a module retain declaration order.

`refresh: ['available']` invalidates named facts in that module after successful
execution, so pending conditions observe the new state. A module dependency is
ordering, not automatic refresh. Declare both when downstream decisions depend
on a producer's changed observations. Provider plugins can supply their own
refresh metadata; consumer declarations still need to name known facts.

## Profiles

```python
{'schema_version': 1, 'name': 'developer', 'modules': ['git', 'zsh']}
```

Profiles explicitly select modules. The listed order is preserved where dependencies
allow it. A missing module is an error; repeated module names are rejected. Profile
selection and explicit CLI module names cannot be combined. Without either selection,
Etch discovers all modules in lexical order.

## Defaults and overrides

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/homebrew'],
  'defaults': {'link': {'create': True}},
  'execution': {'jobs': 2, 'resources': {'package-manager:brew': 1}},
}
```

`defaults.conf` is optional. `plugins` selects source bundles explicitly; it does
not fetch/install them. `defaults` supplies options supported by each provider.
Execution settings control jobs and shared capacities. `--jobs` overrides only the
job count, not resource safety or dependencies.

An action option replaces the matching default. Nested dictionaries are replaced,
not recursively merged: an action's `env` or `tls` replaces that whole configured
provider-default dictionary. Within the resulting `env`, variables override the
inherited process environment individually. An installer `expand_home: False`
can override a `True` default. `link.source_scope` is entry-only and cannot be set
as a default. Provider defaults must use the correct provider name and supported options.
Defaults do not register/select a provider; an unused entry has no effect.
Unsupported options fail when that provider validates the configuration.

## Paths and literals

Destinations expand `~` and anchor relative paths to the consumer root. Link/script
sources anchor to the module and must remain contained there. `link.source_scope:
'repo'` explicitly selects a repository-owned source such as the launcher; it does
not change other entries. Command checks and script execution use the module root.
Plugin roots are relative to the consumer. See [links](filesystem.md) and [commands](commands.md).

String command forms use the host's supported shell; argument lists bypass shell
parsing. `$HOME` in an argument list is literal. Installer `expand_home` optionally
expands a leading tilde in its arguments/configured environment values; this is not
interpolation in arbitrary configuration. Windows strings use escaped backslashes
or forward slashes; see [Windows paths and commands](windows.md).

## Edit, validate and review

```sh
etch format
etch format --check
etch validate
etch doctor --profile developer
etch plan --profile developer
```

The canonical format uses two spaces; short scalar arrays stay inline. EditorConfig
is an editor hint, not a formatter configuration source. Formatting does not prove
that an action is safe or available. Validate declarations, inspect the selected
profile, and review trusted plugin/script code before applying it.
