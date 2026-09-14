# Managed-link cleanup

`clean` removes only receipt-backed links that are broken or explicitly retired.
It does not infer ownership merely because a link points into the repository.

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
local operational state, excluded from Git; they are not transferred as ownership
proof between machines.

Clean requires the current symlink to match that receipt exactly. Missing, malformed,
unreadable or stale receipts provide no permission to delete. Symlinked receipt
directories/files are not trusted. Changed or replaced links lose their ownership
proof. Legacy links created before receipts were introduced remain unowned.

Broken targets qualify automatically once ownership is proven. Valid links qualify
only when explicitly listed in `obsolete`. This avoids removing another module's
configuration merely because the current run selects a partial profile. Removing
a link declaration alone does not automatically retire its old destination.

## Planning and execution

Plans enumerate removal destinations and claim each exclusively. Active link claims,
including SKIP plans, therefore conflict with a clean removal of the same destination.
Compatible shared parent-directory claims remain valid. Such conflicts are errors;
the planner does not silently choose clean over another provider.

Inspection does not delete links or write receipts. Application rechecks receipt
identity for all candidates before the first removal and again before each unlink.
A restored target cancels an automatic broken-link removal; explicit retirement
still applies. Reapplication after removal is a no-op. Receipts for deleted links
may remain as stale records; they confer no ownership on a missing or changed path.

This is conservative provenance, not tamper-proof authorization. Plugin code and
the repository's local state are trusted. Checks are not atomic against concurrent
external filesystem changes; I/O errors can leave a partially applied action.
Likewise, a failure to write a receipt after link creation leaves a link without
cleanup proof and reports the error. Clean preserves anything it cannot prove owned.

Receipt persistence and cleanup behavior are separate modules under
`etchlib/providers/filesystem/`. The executor remains responsible for fresh ownership,
dependency and privilege validation before invoking provider application.
