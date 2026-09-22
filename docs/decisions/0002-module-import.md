# 0002 — Copy-only module imports

Status: accepted in #24; implemented in #25. See [import usage](../importing.md).

Tracks [#24](https://github.com/rm-industries/etch/issues/24), implements the design
boundary from architecture sections 97–100, and guides
[#25](https://github.com/rm-industries/etch/issues/25). Imported content becomes
consumer-owned files, not a managed dependency.

## Command and source identity

The v1 interface will be:

```sh
etch import github:owner/repository --path modules/git --ref refs/heads/main --repo ./consumer
etch import https://example.org/team/dotfiles.git --path modules/git --ref FULL_COMMIT_ID --repo ./consumer
```

`SOURCE` is a single positional argument; `--path` is required. `--repo` defaults
to the current directory. `--ref` defaults to remote `HEAD`. `--no-provenance`
disables the informational sidecar described below. No module/profile selector,
rename flag, force flag, update flag, or dependency-import flag is provided.

- `github:OWNER/REPOSITORY` expands to an HTTPS Git URL. Owner/repository are
  nonempty single components; no path, ref, query or fragment is embedded here.
- Explicit remote sources are public HTTPS Git repository URLs. Reject userinfo,
  query strings, fragments, control characters and non-HTTPS schemes. TLS
  verification is required; redirects are refused. Authentication prompts and
  credential helpers are disabled. Private repositories, SSH/scp syntax, local
  paths, `file:`, `git:`, remote helpers and archive URLs are deferred.
- `--ref` accepts exactly `HEAD`, a validated full `refs/heads/...` or
  `refs/tags/...` name, or a full 40-digit SHA-1 commit ID. Abbreviated object IDs,
  revision expressions and refspec operators are rejected. Short branch/tag
  names are deliberately not guessed. SHA-256 repositories are deferred in v1.
- `--path` is a literal repository-relative POSIX directory path. Reject absolute
  paths, empty components, `.`/`..`, backslashes, control characters and `.git`
  components. No glob/pathspec interpretation, URL decoding or directory search.
  Importing the repository root is not supported.

The path identifies one directory containing `module.conf`, not necessarily a
child of upstream `modules/`. Its basename must be a valid Etch module name and
must agree with an explicit configuration `name`, matching current module rules.
The destination is exactly `<consumer>/modules/<name>`. An import never modifies
profiles, root defaults, declared plugin paths, sibling modules or the consumer's
Git index. Source root defaults do not accompany the module; consumer defaults
will apply during subsequent planning.

## Acquisition and optional tools

Python remains standard-library-only. Import alone requires an installed Git
with shallow-fetch and partial-clone support (minimum Git 2.25). Missing or old
Git produces an actionable error before network access or destination changes;
other Etch commands do not gain a Git requirement. Etch does not install Git or
add a Git/Python dependency package.

Use a temporary bare Git repository, no working-tree checkout, and no archive
extraction. Fetch only the requested ref with depth 1 and no automatic tag or
submodule following. Request `blob:none` filtering, then enumerate the selected
commit subtree with NUL-delimited `git ls-tree` and read required raw blobs by
object ID with `git cat-file`. Fetch the selected blobs in a batch where supported;
do not create one network request per asset deliberately. Do not use textconv,
smudge filters, checkout hooks, LFS downloads, archive export substitutions or
submodule initialization. Unsupported filtering may transfer more objects;
report that fallback instead of claiming only the subdirectory was downloaded.
There is no HTTP archive fallback or second resolution of a moving ref.

Resolve and peel the fetched object to a commit **in the fetched object store**.
Read its full ID there and use that immutable ID for every subsequent tree/blob
operation and provenance. Never label a download with a separate `ls-remote`
result: a branch may move between requests. A supplied full commit must match
exactly. If a server will not supply a requested object, report failure; do not
silently substitute HEAD or search other branches. Annotated tags peel to commits;
tags pointing to trees/blobs are invalid sources.

Run Git using argument arrays, a controlled temporary repository and an isolated
Git configuration/environment. Disable inherited config injection, URL rewrites,
credential/askpass helpers, hooks/templates, replacement objects and interactive
input; allow only the chosen HTTPS transport. Keep TLS verification enabled.
The Git executable and its HTTPS transport are trusted installed tools; imported
scripts/configuration/plugins never run. Global Git aliases, credential helpers
and custom CA/proxy configuration are not an implicit authentication interface.

Implementation must bound acquisition time (120 seconds total), child-output
capture (1 MiB of diagnostic text), selected file count (10,000), per-file size
(16 MiB), and selected total bytes (128 MiB). Check sizes before blob
materialization. Limits produce explicit errors and no completed destination;
no automatic retry. Filtering is an optimization, not a promise to bound all
Git pack traffic or disk usage to the selected subtree. Shared object caches and
persistent clones are deferred; temporary retrieval data is removed on handled
failure and success.

## Validation and publication

Retrieve and validate the entire selected module in temporary storage before
publishing any configuration into the consumer. Reuse literal parsing,
duplicate-key checks, schema/version/name checks and condition/metadata
validation. Never use `exec`, import a module, gather a fact, inspect a provider,
run a check command or build/apply a plan as part of import validation.

Accept regular Git blobs with modes 100644 or 100755, preserving bytes, relative
paths and only the executable distinction (write as 0644 or 0755). Reject symlinks,
gitlinks/submodules, special entries and `.git` components, rather than following
or expanding them. Reject non-UTF-8 names, path traversal, normalization/case
collisions on the target filesystem and an upstream `.etch-import.json` sidecar.
Do not dereference Git LFS pointer files; reject recognized LFS pointers with
instructions to supply ordinary module assets. Hidden ordinary assets are copied;
`.gitattributes` does not transform the selected bytes.

The destination must not exist, even as an empty directory or broken symlink.
Check before retrieval and again at publication; reserve it with exclusive
`mkdir`, not a check followed by replacement. Reject symlinked destination parent
components. There is no merge, overwrite, identical-content exception, automatic
backup or re-import update. Existing files belong to the consumer.

Publish validated assets and optional provenance into the newly reserved directory,
then publish `module.conf` last. Import is a single-writer operation; do not run
other Etch commands against the same consumer during publication. This sequence
does not claim an atomic directory transaction. On handled failure, remove only
the unpublished directory created by this invocation; never touch a pre-existing
destination. Abrupt termination may leave an incomplete directory without
`module.conf`; a retry refuses it and explains that the user must inspect/remove
it before retrying. A completed `module.conf` is never written before all other
content is ready. No imported behavior runs automatically after publication.

Provider-specific payloads and runtime asset references are not fully validated
here: that can require provider code, consumer defaults or machine state. Report
this boundary explicitly. Structural validity is not proof of safety or a
successful apply. After reviewing content, the user can separately run doctor or
plan; those commands load explicitly declared trusted plugins and may run probes.

## Dependencies and executable-content report

Read dependency and provider names as literal data, including inactive branches.
Report module/action `requires`, optional `after`, action provider names and fact
provider names. Classify dependencies against the consumer's existing module
names: missing `requires` means further setup is needed; absent `after` is an
ordering warning. Neither prevents a structurally valid copy, and neither causes
remote resolution, sibling import, profile selection or configuration rewriting.

Compare provider names only against the built-in registry's names. Do not load
consumer or source plugins to discover their exports. Non-core names are reported
as **not supplied by core; plugin availability unverified**, with the action/fact
location and instructions to review/install/declare the required plugin explicitly.
Do not invent a plugin package name from a provider name. Even an existing consumer
plugin declaration is not proof that a provider is available or compatible.

Always print a review summary, before the final success message, containing:

- Canonical source, requested ref, resolved commit, source path and destination.
- Core versus unverified external providers, missing dependencies and the fact
  that only structural validation occurred.
- Locations of shell, script and installer actions, installer URLs, executable-bit
  files, and any `.py`/`etch_plugin.py` files. Never print entire scripts, payloads
  or environment values. Escape control characters in displayed remote text.
- A reminder that any provider may implement executable behavior, even when no
  known executable marker was found. Script extensions/mode bits are inventory,
  not a proof that all executable content was detected.

Reports are informational and do not install or activate code. Successful copy
returns 0 even with setup warnings; invalid input, acquisition/validation failure,
or publication failure returns 1 (argument syntax errors return 2). A failed
structural import leaves no completed module, and failure messages identify the
stage and offending ref/path without exposing credentials or arbitrary payloads.

## Provenance and consumer ownership

Write `.etch-import.json` inside the imported module by default. It is data only;
Etch's module loader ignores it. The importer creates it, never trusts upstream
metadata, and omits it under `--no-provenance`.

```json
{
  "schema_version": 1,
  "source": "https://github.com/owner/repository.git",
  "requested_ref": "refs/heads/main",
  "resolved_commit": "0123456789abcdef0123456789abcdef01234567",
  "source_path": "modules/git"
}
```

The example commit is illustrative. The resolved fetched commit, not the ref name
or upstream metadata, identifies the origin snapshot. This is provenance, not a
signature, trust guarantee or assertion that locally edited files still match it.
No timestamp is required: pinned imports into different empty consumers produce
the same file bytes/modes and metadata. With `--no-provenance`, print the resolved
commit in the summary so the user can retain it separately.

There is no registry, lockfile, automatic update, synchronization, dependency
solver or link back to upstream. Consumers edit the copied files normally.
Updating means an explicit separate import into a disposable consumer and a
human-reviewed comparison; v1 never replaces existing modules.

## Implementation acceptance in #25

Tests must cover moving refs versus resolved provenance, pinned repeatability,
annotated tags, unavailable refs, invalid/ambiguous source syntax, optional Git,
filter fallback, missing or malformed modules, duplicate keys, mode preservation,
unsafe/colliding paths, unsupported tree entries, non-executing provider reports,
existing destinations, resource limits and interrupted retrieval/publication.
Use fake transport and local test object stores through the test harness without
adding local transport to the production CLI. Exercise Python 3.9+ on Linux/macOS.
The implementation covers these boundaries with local Git object stores and a
test-only transport substitution; production accepts public HTTPS only.

## Git references

The acquisition design uses the documented object interfaces:
[fetch](https://git-scm.com/docs/git-fetch),
[ls-tree](https://git-scm.com/docs/git-ls-tree), and
[cat-file](https://git-scm.com/docs/git-cat-file).
