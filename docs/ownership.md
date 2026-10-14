---
title: "Destination ownership and activation validation"
description: "Understand destination conflicts and why satisfied or shared paths still matter."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Destination ownership and activation validation

Each active destination has one exclusive owner. A provider may instead declare
a `SHARED_DIRECTORY` requirement: creating a directory does not recursively own
everything beneath it. Claims describe managed paths, not execution resource locks.

## Conflict rules

- Two exclusive claims at the same path conflict, even if either plan is SKIP.
  Satisfied configuration still has an owner.
- An exclusive ancestor conflicts with another action's descendant claim. This
  prevents replacing a directory or link while another action manages its subtree.
- Shared directory requirements at the same path are compatible. Shared ancestors
  can contain independently owned files and directories.
- Sibling paths do not conflict. Repeated claims from the same action retain the
  same owner; providers validate the internal consistency of their own plan.

Normalization compares lexical absolute paths and paths with symlinked parents
resolved. The final component of an exclusive claim is preserved: managing a
symlink does not claim its current target. Shared-directory claims also follow the
final symlink to detect aliases of a directory. Existing parent files, non-directory
shared targets, broken shared-directory symlinks and path-resolution errors fail.
Nonexistent directories are permitted as planned future state.

Providers should supply absolute destination paths and use the same paths in their
application logic. The checks do not infer arbitrary script side effects, hard-link
content sharing or case-folding aliases on case-insensitive filesystems. Those are
limits of path-based ownership; providers must not advertise claims that conceal
the effects of their actions. Filesystem state may change after a snapshot, so
providers still need state inspection and defensive application logic.

## Newly active work and failures

False or deferred actions do not claim destinations until they become active.
After a successful producer refreshes a fact, Etch reevaluates pending conditions
and validates newly active paths, dependencies and privilege requests before running
that work. Claims from completed and already-satisfied actions still participate.
A newly active action cannot take ownership of a path another selected action owns.

`--allow-sudo` authorizes declared elevation for the invocation, including newly
active actions; it does not bypass ownership checks. More parallel jobs do not
permit conflicting owners or authorize arbitrary script side effects.

These checks do not create a filesystem transaction. Providers recheck current
state before mutation, but outside processes can still change it. Earlier effects
are not rolled back on failure. See [applying](applying.md), [cleanup](clean.md) and
[scheduling](scheduling.md) for operational behavior.
