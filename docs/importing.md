# Importing a module

Import copies one module from a public HTTPS Git repository into your existing
consumer. It does not apply actions, probe facts, load plugins, install packages,
select a profile or update existing files.

```sh
./etch import github:owner/dotfiles --path modules/git --repo ~/dotfiles
./etch import https://example.org/team/dotfiles.git \
  --path shared/git --ref refs/tags/v1 --repo ~/dotfiles
```

The source directory basename is the module name. Both commands above copy into
`~/dotfiles/modules/git/`; `module.conf` must declare `name: "git"` using the normal
literal configuration syntax. The source layout is independent of the fixed
consumer `modules/` layout. The destination must not exist, even as an empty
directory or symlink. Inspect and remove an old/incomplete destination yourself
before retrying; there is no force, rename, merge or update option.

## Requirements and refs

Only import needs Git 2.25 or newer. Core still uses Python 3.9+ and the standard
library; other commands do not require Git. The consumer directory must already
exist. Symlinks in its destination parent chain are rejected; use the physical
path when the repository is reached through a symlink.

`--ref` defaults to remote HEAD. To pin a branch/tag, use `refs/heads/main` or
`refs/tags/v1`, or supply the full 40-character commit ID. Short names, abbreviated
hashes and revision expressions are rejected. Annotated tags are peeled to their
commit. Unsupported or inaccessible objects fail rather than falling back to
another ref. SHA-256 Git repositories are not supported yet.

Sources accept `github:OWNER/REPOSITORY` or an explicit HTTPS Git URL. Private
repositories, embedded credentials, query/fragment syntax, SSH, local paths and
archive URLs are unsupported. TLS verification remains enabled; redirects,
interactive authentication, credential helpers and inherited Git customization
are disabled. This intentionally does not inherit custom CA/proxy settings or
URL rewrites from your Git configuration.

## Copy and validation boundaries

Etch fetches a shallow snapshot into temporary storage, without a checkout. It
requests blob filtering and fetches selected blobs in batches of up to 256 object
IDs. When filtering is unavailable, it reports that extra data was transferred.
All subsequent reads use the resolved commit, even if the branch moves. It does
not use Git hooks, checkout filters, LFS downloads or submodule initialization.

Files retain their bytes, relative locations and executable distinction. Import
rejects symlinks, submodules, LFS pointers, unsafe paths, reserved provenance,
and case/Unicode-normalization collisions. Collision rejection is conservative
on every platform so the same module remains portable to macOS and Linux.

Structural checks reuse the configuration loader and condition validator. They
cover literal syntax, duplicate keys, schema/version, module identity and generic
metadata. Provider-specific payloads, referenced assets, runtime state and consumer
default composition are not certified. The source's root defaults and profiles
are not copied. Module-relative assets remain inside the copied module.

The report lists action/fact provider names, dependency names and known executable
markers. Non-core providers are labeled “not supplied by core; plugin availability
unverified.” Etch cannot verify them without loading plugins, so it does not
claim they are definitely missing or infer a package to install. Missing hard
requirements and optional ordering dependencies are reported without fetching or
selecting other modules. Existing consumer modules are identified by their
`modules/<name>/module.conf` paths, not executed or fully validated.

Review the copied files before running `doctor` or `plan` separately: those
commands may execute probes and explicitly declared plugin code. Executable-bit
files, Python files and shell/script/installer actions are identified, but this
inventory is not a safety certification. Installer URLs are displayed without
credentials or query parameters. Payloads and whole scripts are not printed.

## Provenance, limits and failure

By default, `.etch-import.json` records the canonical source, requested ref,
authoritative resolved commit and source path. `--no-provenance` omits the file;
the resolved commit still appears in output. No timestamps are recorded, allowing
repeatable pinned copies. The sidecar is informational: local edits are yours,
and it does not guarantee authenticity or describe your edited content.

The complete module is retrieved and structurally validated before publication.
Etch exclusively creates the destination, publishes assets/provenance, then
renames the completed `module.conf` into place last. Handled failures remove only
the newly reserved directory. A hard interruption may leave an incomplete
directory; inspect it before removal/retry. Do not run concurrent operations
against that consumer during publication. This is not an atomic directory
transaction and imports never automatically apply afterward.

Acquisition has a 120-second total deadline and a 1 MiB diagnostic/metadata capture
limit. Selected content is limited to 10,000 files, 16 MiB per file and 128 MiB
total before materialization. Git may download more pack data, particularly when
filtering is unsupported; these are not bounds on all network or temporary disk
usage. Timeouts terminate Git's helper process group. There are no automatic
retries or persistent caches.

Exit 0 means a structurally valid copy succeeded, possibly with setup warnings.
Exit 1 means input, acquisition, validation or publication failed. Argument syntax
errors exit 2. To compare a future upstream version, import into a separate empty
consumer and review the difference. There is no registry, lockfile, dependency
solver, automatic update or implicit synchronization.

The [design decision](decisions/0002-module-import.md) records the contract.
