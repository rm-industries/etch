---
title: "Managed-link cleanup"
description: "Remove only broken or retired links whose ownership Etch can prove."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Managed-link cleanup

Etch automatically manages the lifecycle of links it created. Its ignored
`.etch/links/` receipts record ownership so old destinations can be retired
without maintaining a growing list of obsolete paths.

## Automatic retirement and housekeeping

When a selected, active module removes a link declaration or changes its
destination from A to B, `plan` previews retirement of A. After a successful
`apply`, Etch removes A only if it still matches its recorded link identity,
then deletes the receipt. B is reconciled normally before retirement runs.
A destination still declared by another module is preserved.

A full run without module arguments or `--profile` can also retire links from
module directories actually removed from the repository. Partial/profile runs
preserve those modules' records. An existing module directory without its
configuration is treated as unavailable, not as a proven removal. Git sparse
exclusions and uninitialized submodules are also preserved; unavailable or failed
Git checks provide no authority to retire a missing module.

False or deferred module conditions, incomplete catalogs, failed planning, and
failed/partial applies do not authorize retirement. User-replaced links and
ordinary files are preserved. Removing a declaration is distinct from merely
omitting a module from a profile or temporarily disabling an action condition.

Housekeeping runs automatically; no `clean` action is required for it. It prunes
receipts for missing/replaced links, invalid receipt JSON, and missing downloaded
files. It preserves useful ownership records. It does not recursively scan user
directories, contact the network or hash downloaded contents to find orphans.
Planning only reports the work. Apply rechecks configuration, destinations and
receipt identity before deletion; refreshed receipts are preserved. If eligibility
only becomes known after a fact refresh, cleanup can wait for the next run.

Even a checkout with no remaining modules can run plan/apply for housekeeping
when `.etch/` already exists. This does not turn an arbitrary empty directory
into a valid configuration repository.

## Explicit cleanup actions

User-defined `clean` actions remain supported alongside automatic housekeeping.
They remove only receipt-backed links that are broken or explicitly retired,
subject to the active destination claim checks described below.
They do not infer ownership merely because a link points into the repository.

```python
{"clean": ["~", "~/.config"]}
{"clean": {"paths": ["~/.config"], "obsolete": ["~/.config/old-tool"]}}
```

Paths select directories; scanning is limited to their immediate children. Nested
directories are not traversed, and symlinks used as scan roots are rejected. Explicit
obsolete destinations must be immediate children of a selected root. Missing roots
are harmless. No provider defaults are currently supported.

## Ownership evidence

After creating or explicitly relinking a symlink, `link` writes a schema-versioned
receipt beneath the consuming repository's `.etch/links/`. The receipt records its
absolute destination, literal target, device/inode identity, change timestamp and
originating module. A preexisting already-correct link is not adopted. Receipts are
local operational state in the consumer checkout, excluded from Git; they are
not transferred as ownership proof between machines. Keep `.etch/` in the
consumer's `.gitignore` (the template already does). Deleting it discards cleanup
proof; it is not a cache that Etch can safely rebuild by adopting existing files.

Clean requires the current symlink to match that receipt exactly. Missing, malformed,
unreadable or stale receipts provide no permission to delete. Symlinked receipt
directories/files are not trusted. Changed or replaced links lose their ownership
proof. Legacy links created before receipts were introduced remain unowned.

For an explicit `clean` action, broken targets qualify automatically once ownership
is proven. Valid links qualify when explicitly listed in `obsolete`. This avoids removing another module's
configuration merely because the current run selects a partial profile. Automatic declaration
retirement is handled separately by the lifecycle described
above; explicit `obsolete` entries remain useful for deliberate cleanup.

## Planning and execution

Plans enumerate removal destinations and claim each exclusively. Active link claims,
including SKIP plans, therefore conflict with a clean removal of the same destination.
Compatible shared parent-directory claims remain valid. Such conflicts are errors;
the planner does not silently choose clean over another provider.

Inspection does not delete links or write receipts. Application rechecks receipt
identity for all candidates before the first removal and again before each unlink.
A restored target cancels an automatic broken-link removal; explicit retirement
still applies. Successful removal also removes the matching receipt; if the
link disappeared after planning, cleanup can remove only its stale receipt.
Reapplication after removal is a no-op. Explicit actions retain normal module
ordering and failure behavior; automatic retirement waits until apply succeeds.

This is conservative provenance, not tamper-proof authorization. Plugin code and
the repository's local state are trusted. Checks are not atomic against concurrent
external filesystem changes; I/O errors can leave a partially applied action.
Likewise, a failure to write a receipt after link creation leaves a link without
cleanup proof and reports the error. Clean preserves anything it cannot prove owned.
