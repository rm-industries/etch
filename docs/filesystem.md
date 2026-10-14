---
title: "Directory and link providers"
description: "Create directories and link owned sources with explicit conflict and path behavior."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Directory and link providers

Use `create` to ensure directories exist and `link` to connect module-owned files
to their destinations. Plan and doctor inspect them without changing files; apply
rechecks current state before making changes and skips already-correct state.

## Create

```python
{"create": ["~/.config", "~/.local/bin"]}
```

Create accepts a nonempty list of directories and creates missing parent directories.
Existing directories and symlinks to directories are satisfied. Files and broken
symlinks are errors and are never replaced. Claims are shared directory requirements;
other providers may independently own files beneath them. No default options are
currently accepted for create.

## Link

```python
{"link": {"~/.gitconfig": "files/gitconfig"}}
{"link": {"~/.config/tool/config": {
  "path": "files/config", "create": True, "relink": True,
}}}
```

Sources are existing module-relative assets, contained within the module root.
Existing string and dictionary entries retain this default. Explicitly set
`source_scope: "repo"` on an entry to select a source relative to the consumer
repository instead, for example its repository-owned launcher:

```python
{'link': {'~/.local/bin/etch': {
  'path': 'etch', 'source_scope': 'repo', 'create': True,
}}}
```

Repository-scoped sources must resolve inside the consumer checkout, including
through symlinks, and containment is rechecked before applying. Absolute and
escaping sources are rejected. This option is entry-only: it cannot change
source interpretation through provider defaults. Plan/doctor show the source
for repository-scoped links. Existing parent creation, conflict refusal, relink,
receipts and ownership rules still apply. No schema-version or format change is
required for existing configurations.

Use the template's symlink-aware consumer launcher before exposing it through a
user-local link. The core engine alone does not infer its consumer from that link. Installing a link does not
add its directory to PATH or modify any shell startup file.
When a linked directory contains Git submodules, inspection checks their pinned
checkouts before planning or applying the link. Missing, uninitialized, or
different revisions report the affected path and the Git initialization command;
Inspection never initializes submodules. Use the explicit update commands when needed. See [submodule-backed assets](submodules.md)
for a Vim/tmux migration layout.
Destinations use the common destination resolver. Links point to the resolved
absolute source; moving a module and planning again uses its new location.
An existing equivalent link is SKIP. A missing destination is created. Different
or broken symlinks require `relink: True`; files and directories are never replaced.
By default, `target_match: "resolved"` treats links through intermediate symlinks
as equivalent. Set `target_match: "direct"` to compare the immediate symlink
target with the module asset without following intermediate links. Relative
targets are normalized against the destination's parent. An aliasing legacy
link then requires `relink: True` to replace it; without `relink`, it reports
the different-link error.
Successful creation/relinking records local ownership for the
[clean provider](clean.md).
Already-correct links are not automatically adopted.
`create: True` allows missing destination parents to be created. `create` and
`relink` default to False; `target_match` defaults to `"resolved"`. All three
can be set in provider defaults:

```python
{"schema_version": 1, "defaults": {"link": {"target_match": "direct"}}}
```

Each link entry overrides those defaults independently. Unknown options,
non-boolean `create`/`relink`, invalid `target_match` values,
missing or escaping sources, duplicate or nested destinations, and destinations
that overwrite sources in the same action fail validation. Recursive directory
links into their own source are rejected. Each destination has an exclusive claim;
automatic parent creation adds a shared directory claim.

## Application and limits

Application rechecks every destination in an action before making its first change,
including when applying a previously satisfied plan. It refuses changed parent
resolution and regular files that appeared since planning. Repeated application of
unchanged desired state returns `changed=False`.

These are defensive checks, not filesystem transactions. Relinking creates a candidate link before replacing the old link;
a later I/O or receipt-write failure can still leave partial changes.
Concurrent external filesystem changes remain possible between inspection and
mutation. Apply validates ownership and dependencies before execution. Source aliases and
changed destination parents are rechecked rather than treated as stable paths.
