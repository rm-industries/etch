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

## Fresh validation after activation

`validate_snapshot(repository, selections, registry, facts, fact_links,
elevated_actions)` processes the current condition results. For every TRUE action
in a TRUE module it resolves the provider, validates configuration, inspects state
and obtains a new normalized plan. It then checks action-specific privilege
authorization, rebuilds and cycle-checks the graph, and validates all active claims.
There is no cached-plan argument and no call to provider apply.

FALSE and DEFERRED actions do not contribute ownership claims. Reevaluate conditions
after refresh, then call this API again before newly active work is executed. An
invalid provider, payload, path, dependency, privilege request or overlapping claim
prevents the snapshot from being returned. Unchanged active actions are revalidated
too, including their ownership of already-satisfied destinations.

Privilege defaults to disallowed. The caller can supply the exact `NodeId`s whose
elevation has been authorized; this API neither prompts nor invokes sudo. The
executor must preserve the authorization context and scheduling constraints.

The returned snapshot contains plans, normalized claims and the validated graph.
It is evidence for the planner/executor, not an apply capability or a guarantee that
the filesystem cannot change. Planner orchestration, execution, race handling and
clean-provider ownership provenance remain separate issues.

Claim normalization/conflict checks and snapshot orchestration live in separate
modules under `etchlib/ownership/`.
