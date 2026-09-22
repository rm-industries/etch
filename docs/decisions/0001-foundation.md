# 0001 — Foundation and initial contracts

Status: proposed for review; configuration-loading choices implemented in this branch.

Source: [architecture baseline](https://github.com/rm-industries/etch/issues/1).
Tracks [#3](https://github.com/rm-industries/etch/issues/3). This record distinguishes
implemented foundation behavior from contracts to implement in subsequent issues.

## Runtime and repository

Use an executable root `etch` launcher and an importable `etchlib/` package to avoid
a filename/package collision. Core and official examples use Python 3.9+ and only
the standard library. Initial execution targets are Linux and macOS. Windows
support is deferred pending filesystem/privilege semantics and platform tests.
Tests use unittest. CI checks the minimum and a newer interpreter on both targets.

`etchlib.__version__` stores the release version; schema and plugin API versions
are independent integer constants. A checkout must run with site packages disabled.

## Configuration and selection

Use `defaults.conf`, `modules/<name>/module.conf`, and `profiles/<name>.conf`.
Every file is a literal dictionary declaring integer `schema_version: 1`.
Module/profile names match their directory/filename. Profiles contain an ordered
`modules` list. Module actions are ordered dictionaries; providers validate their
own payloads in #6. Module conditions, facts, requires and after retain the source
document's forms. Exact provider option schemas are owned by their implementation issues.

The root defaults document will hold `plugins: ["vendor/etch-vscode"]` and
`defaults: {"link": {...}}`. Each provider declares which options accept defaults.
An action overrides individual allowed default keys; lists replace rather than
concatenate, and nested merge is unsupported unless a provider documents it.
The loader checks defaults shape; `compose_defaults` provides opt-in atomic replacement
for provider implementations. Providers opt in during their own option normalization.

Use `etch <command> [module ... | --profile NAME] --repo PATH`. Both selectors
together are invalid. No implicit profile is applied. Doctor inspects all modules
when no selector is supplied; plan/apply will require explicit selection until a
default-profile policy is accepted. Discovery validates every module's structural
identity, including unselected modules; provider applicability is resolved later.

Assets resolve against the module root. Absolute paths, traversal and resolved
symlink escapes are rejected by the asset resolver. Destination expansion is
handled by a separate resolver: expand `~`, anchor relative paths at the consumer
root, resolve parents and preserve the final symlink. Providers must use this shared
resolver rather than the asset resolver for user-owned destinations. Ownership and
conflict semantics remain provider/planner work.

## Provider contracts and plugin loading

The shared registry and result types are implemented; see
[provider contracts](../providers.md). Explicit [plugin loading](../plugins.md)
and API compatibility checks are also implemented.

Separate ActionProvider and FactProvider protocols. Core registers providers
through the same registry as external bundles, without a public/internal plugin
loader dependency. Provider names are unique, flat identifiers initially.

ActionProvider responsibilities: validate(config, context), inspect(config, context),
plan(config, observation, context), and apply(plan, context). Normalized immutable
result records carry status, description, dependencies, claims, refresh references,
execution resources, privilege, network requirements and opaque-side-effect flags.
Inspection returns satisfied/change/unknown with provider-owned observed data;
planning returns skip/change/run with a provider-owned payload. Exact Python field
types will be tested in #6 before the plugin API is declared stable.

FactProvider gathers a normalized VALUE/UNAVAILABLE/STALE/ERROR result including
value and reason. Fact references are resolved by `(module_name, local_fact_name)`;
provider type names and scoped fact instance names are distinct. Public output may
render module-qualified names; do not parse qualified names by guessing dot splits.

Explicit plugin paths identify roots containing `etch_plugin.py`. That trusted code
exports PLUGIN metadata (name, version, api) and `actions()` / `facts()` factories.
There is no environment discovery, dependency solver, alias registration or override.
Plugins remain executable trusted code, including during diagnostic loading.
Metadata compatibility is checked before provider registration or application,
not advertised as preventing execution of an incompatible plugin's entrypoint.
Reference plugins start under `plugins/` as separately loaded bundles while the
API stabilizes; consumers can vendor them. Dedicated distribution repos can follow.

## Ownership, ordering and staged validation

Filesystem claims begin with exclusive managed destinations and compatible shared
directory-creation requirements. Do not add non-filesystem claims yet. #12 must
specify ancestor/descendant and symlink normalization before #13–#14 mutate files.
Clean must establish evidence of managed ownership; absence of evidence means
preserve. The proof mechanism is delegated to #14 rather than assuming every broken
link is managed. Directories are not recursively owned simply because Etch creates them.

`requires` must be local and active; `after` orders active references and emits a
warning for missing/inactive names. Stable declaration order breaks scheduling ties.
Explicit refresh is authoritative. #11/#18 determine producer edges and lazy refresh;
newly active nodes always receive complete validation before application.
Providers report resources as strings, initially `package-manager:<name>`,
`application:<name>`, `sudo-interactive`, and `network`. #19 owns capacities and
interactive privilege scheduling. A resource name is not a destination ownership claim.

## Complete disposition of section 142 questions

| Open question | Initial disposition |
| --- | --- |
| Configuration extension | `.conf`, implemented here |
| Source layout | root launcher + etchlib, implemented here |
| Schema syntax | literal versioned dictionaries; outer shape here, provider payloads #6/#13–#16 |
| Defaults composition | declared option keys; action replacement; implement with providers |
| Repository-relative escape hatch | deferred; module-owned assets stay contained |
| Profile conditions | deferred; module/action conditions suffice initially |
| CLI syntax | command-local selectors and --repo, as above |
| Git import syntax | #24 |
| Efficient subdirectory import | #24 |
| Optional dependency import behavior | #24; no implicit fetching |
| Missing after warning | warn and ignore absent/inactive target; #11 |
| Clean/create ownership | conservative rules above; concrete proof/overlaps #12–#14 |
| Provider base interfaces | separate action/fact protocols above; exact types #6 |
| Shared action/fact protocol | no shared mandatory execution protocol |
| Plugin entrypoint | etch_plugin.py; #7 |
| Plugin declaration syntax | explicit plugins path list in defaults.conf; #7 |
| Plugin root structure | entrypoint plus plugin-owned files; #7 |
| Metadata format | Python PLUGIN constant; #7 |
| Multiple aliases | deferred |
| Provider namespacing | deferred; flat unique registry names |
| Provider overrides | excluded initially |
| Core promotion process | preserve name/schema, remove external declaration; policy #27/#30 |
| Core as internal plugin bundle | direct registry registration, same provider protocols |
| Reference plugins in monorepo | initially yes, externally loaded bundles; #20/#21 |
| providers command in v1 | deferred; origin visible in plan/doctor |
| plugins command in v1 | deferred; compatibility visible in plan/doctor |
| Inspection result types | normalized state plus observed data; finalize #6 |
| Plan result types | normalized metadata plus apply payload; finalize #6 |
| Claim hierarchy | filesystem destinations/shared directories; #12 |
| Non-filesystem claims | deferred until a concrete integration needs them |
| Execution resource naming | names above; #19 |
| Resource concurrency configuration | #19 |
| Plugin fact namespacing | scoped instances distinct from provider types; #8 |
| Plugin fact refresh semantics | same stale/lazy refresh path as core; #18 |
| Provider-inferred refresh | explicit refresh first; narrowly proven derivation #21 |
| Version extraction | First version token on first nonempty line; stdout then stderr; see [version decisions](../versions.md) |
| Version suffix comparison | Single-letter patch suffixes after unsuffixed release, numeric patch counters; see [version decisions](../versions.md) |
| Fact dependency relationships | #11/#18 |
| Installer schema | #16 |
| Installer timeouts/retries | #16 |
| Redirect policy | #16 |
| Checksum behavior | #16; mismatch must prevent execution |
| Parallel privilege | #19; normal user by default |
| Package-manager batching | #21 |
| VS Code removal | deferred initially; install missing only, #20 |
| Package upgrades vs presence | presence initially, #21 |
| One-time YAML migration tooling | deferred; manual migration guide #29 |
| Website domain | #28 |

## Current limits

Runtime, structural loading, shared provider contracts, planning, staged apply,
resource scheduling, and facts/doctor diagnostics are implemented. Doctor loads
explicitly declared trusted plugin code and inspects selected state without
applying actions. Deferred actions require fresh validation after refresh;
opaque command outcomes cannot be certified. Defaults are not automatically
composed by the loader; providers opt into the composition helper.

## Module sharing

[Decision 0002](0002-module-import.md) specifies source/ref/path syntax, copy boundaries and provenance for module
imports, implemented in #25. The existing consumer module layout is unchanged.
