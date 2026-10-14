---
title: "Submodule-backed assets"
description: "Initialize pinned assets and update a consumer from an exposed launcher."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Submodule-backed assets

Keep submodule pins in your own dotfiles repository and place each linked tree
inside its Etch module. For a repository that previously linked `editors/vim`
to `~/.vim` and `terminals/tmux` to `~/.tmux`, move those trees into module-owned
directories while preserving their Git gitlinks and `.gitmodules` entries:

```text
modules/
  vim/
    module.conf
    files/
      bundle/Vundle.vim/        # Git submodule, not copied plugin files
      pack/.../start/.../       # existing pinned Git submodules
  tmux/
    module.conf
    files/
      plugins/tpm/              # Git submodule
```

Configure the Vim and tmux `link` actions to use `path: "files"` and destinations
`~/.vim` and `~/.tmux`, respectively. Keep each module's regular configuration
files beside its submodules. Git must record the moved paths as gitlinks at the
new locations; changing the directory tree alone does not move the pins.

After cloning the consumer repository, run `git submodule update --init --recursive`
there before `etch plan`, `etch doctor`, or `etch apply`. These commands check the
linked source for missing, uninitialized, and non-pinned submodule revisions and
report the offending path. These inspection commands do not fetch or initialize
submodules, and do not change the home directory. An initialized source links
normally; existing destination conflict and repeat-apply rules are unchanged.

`etch import` continues to reject gitlinks. Import copies a self-contained
module snapshot and cannot preserve a submodule pin without adding a separate
Git dependency and checkout policy. Keep these modules in the consumer repository
and initialize them with Git instead of importing them.

`etch doctor` also performs a read-only repository-wide check before loading
consumer configuration or plugins. This catches missing or uninitialized
submodules even when they are not used by a selected link action, including new
submodules added by a pulled change. Non-pinned revisions and merge conflicts are
reported with the affected paths and initialization guidance. No fetch, checkout,
or initialization is performed. Git is needed for the full submodule audit; when unavailable, doctor warns that
submodules were not verified without requiring Git just to run the initialized
engine. Repositories without `.gitmodules` skip the audit. Resolve merge
conflicts before running the suggested recursive update command. A missing engine
still prevents the consumer launcher from starting and is reported by the
launcher itself.

## Initialize from any directory

Once the consumer's pinned engine can start, use the explicit setup command:

```sh
etch submodules update
etch submodules update --repo /path/to/consumer
```

A symlink-aware consumer launcher selects its own checkout even when invoked
from another directory. When running the engine directly, the default repository
is the current directory; `--repo` must select the consumer Git repository root.
The command delegates to `git -C <root> submodule update --init --recursive`,
without reading module configuration, loading consumer plugins or applying actions.
Git's progress, authentication prompts and errors remain visible, and its failure
exit status is returned. Git is required for this explicit setup command only.

This initializes missing/nested checkouts and aligns them to the consumer's
recorded pins. It does not advance gitlinks to newer upstream branches, use
`--remote`/`--force`, stage changes, commit, or discard dirty worktrees. Network
access and worktree changes may occur; resolve Git's reported conflicts yourself.
If the engine submodule changes, this invocation exits after setup rather than
continuing with configuration actions. Rerunning already-aligned setup is safe.
No setup runs implicitly during plan, doctor, apply or launcher startup.

If the engine itself is absent, `etch` cannot provide this command yet. Bootstrap
with `git submodule update --init --recursive` from the checkout, as the launcher
instructs. Doctor retains that raw command and also offers the Etch equivalent.

## Pull the consumer and synchronize its pins

Use `etch update` for a one-stop consumer update:

```sh
etch update
etch update --repo /path/to/consumer
```

The exposed consumer launcher selects its own checkout from any directory.
Direct engine invocation uses the current directory unless `--repo` selects the
consumer Git root. No module configuration or consumer plugin code is loaded.

Etch delegates to `git -C <root> pull --ff-only --no-rebase --autostash
--no-recurse-submodules`, using the current branch's configured upstream. After
success, it checks for unresolved conflicts and runs the same pinned recursive
synchronization as `etch submodules update`. The latter does not pull the consumer.
Submodules are aligned every time; no `--remote`, forced checkout, staging or
commit is performed. Configuration is not applied automatically afterward.

Git temporarily stashes tracked local edits and restores them according to its
autostash semantics. Untracked files are not stashed. Divergence, missing upstream,
authentication problems and untracked-file collisions remain Git errors; its
output and failure status are preserved. No fallback merge, rebase or retry occurs.
Git may report a successful pull even if restoring local edits conflicts; Etch
stops before submodule synchronization in that case. Resolve the reported conflicts
and inspect Git's retained stash yourself. Existing conflicts also stop setup.

This is not an atomic transaction: the consumer can be fast-forwarded before a
restoration conflict or submodule failure. Dirty submodules can prevent alignment,
and newly pulled `.gitmodules` entries can fetch their recorded remotes. Only run
this explicit command for a consumer/upstream you trust. Inspect Git's diagnostics;
Etch does not reset the checkout, drop stashes or undo a successful pull.

Git must support these pull options. Initialization remains necessary before the
engine can start. The small Git helpers are imported before updating; the command
exits after synchronization so the next invocation loads the new engine entirely.
