# Directory and link providers

`create` and `link` register as core action providers through the shared registry.
They validate and inspect without mutation, produce CHANGE/SKIP plans with ownership
claims, and implement idempotent application. The CLI executor remains upcoming work.

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
When a linked directory contains Git submodules, inspection checks their pinned
checkouts before planning or applying the link. Missing, uninitialized, or
different revisions report the affected path and the Git initialization command;
Etch never runs that command itself. See [submodule-backed assets](submodules.md)
for a Vim/tmux migration layout.
Destinations use the common destination resolver. Links point to the resolved
absolute source; moving a module and planning again uses its new location.
An existing equivalent link is SKIP. A missing destination is created. Different
or broken symlinks require `relink: True`; files and directories are never replaced.
Successful creation/relinking records local ownership for the [clean provider](clean.md).
Already-correct links are not automatically adopted.
`create: True` allows missing destination parents to be created. Both options default
to False and can be set in provider defaults:

```python
{"schema_version": 1, "defaults": {"link": {"create": True, "relink": False}}}
```

Each link entry overrides those defaults independently. Unknown/nonboolean options,
missing or escaping sources, duplicate or nested destinations, and destinations
that overwrite sources in the same action fail validation. Recursive directory
links into their own source are rejected. Each destination has an exclusive claim;
automatic parent creation adds a shared directory claim.

## Application and limits

Application rechecks every destination in an action before making its first change,
including when applying a previously satisfied plan. It refuses changed parent
resolution and regular files that appeared since planning. Repeated application of
unchanged desired state returns `changed=False`.

These are defensive checks, not filesystem transactions. Relinking removes the old
symlink and creates its replacement; a later I/O failure can leave partial changes.
Concurrent external filesystem changes remain possible between inspection and
mutation. The executor must validate ownership/dependencies before apply and respect
resource constraints; these providers do not supply an independent execution engine.

Directory behavior, link behavior and shared filesystem inspection live in focused
files under `etchlib/providers/filesystem/`. `etchlib/core.py` composes core actions
and facts; provider-specific dispatch is not added to the executor.
