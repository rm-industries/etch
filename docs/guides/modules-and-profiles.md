---
title: Modules and profiles
description: Keep capabilities small and compose the configuration your environment needs.
publishedAt: 2026-09-22T11:00:00Z
tags:
  - Etch
  - Configuration
draft: false
---

A module owns one capability and its input files. A profile selects modules for a
purpose, such as a developer environment. Both live in your consumer repository.

## A module is local configuration

The starter keeps Git configuration under `modules/git/`. Its `module.conf`
declares a name, schema version, and actions; `files/gitconfig` is a module-owned
asset. Etch reads literal configuration data rather than executing it as Python.

Repository-wide `defaults.conf` holds default provider options and explicit plugin
paths. Actions can override supported defaults. Profiles live under `profiles/`.

## Select deliberately

```sh
./etch plan git
./etch plan --profile developer
```

Dependencies describe ordering and required selected modules. They do not silently
select modules or fetch remote dependencies. Imports copy a module into the fixed
`modules/<name>/` destination and refuse an existing destination.

See the [configuration reference](https://github.com/rm-industries/etch/blob/main/docs/decisions/0001-foundation.md)
and the [import guide](https://github.com/rm-industries/etch/blob/main/docs/importing.md)
for current syntax and limits.
