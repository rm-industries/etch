# Etch performance review

Review date: 2026-10-14. This covers the CLI, planner, graph, scheduler,
providers, configuration tooling, import/update commands, website and CI.
The goal is fast ordinary use without weakening ownership, freshness or failure
handling. This is a review of the candidate in PR #156, not a promise about every
consumer or machine.

## Evidence and limits

The most useful measurements are from the unchanged dotfiles developer profile
on disposable GitHub runners. Candidate `9714d74`, run
[38562740838](https://github.com/rahul0705/dotfiles/actions/runs/38562740838),
passed all four jobs. Its earlier diagnostic baseline is
[38560174416](https://github.com/rahul0705/dotfiles/actions/runs/38560174416).

| macOS measurement | Baseline, Python 3.9 / 3.x | Optimized candidate, Python 3.9 / 3.x |
| --- | --- | --- |
| Fresh apply elapsed | 416.004s / 448.560s | 397.534s / 386.558s |
| Provider execution | 374.498s / 416.340s | 389.425s / 379.027s |
| Provider inspection | 39.200s / 29.805s | 5.966s / 5.446s |
| Repeat apply, no executed actions | 6.643s / 9.410s | 2.841s / 3.154s |
| Initial plan elapsed | 12.048s / 10.511s | 9.112s / 6.716s |
| Oh My Zsh link inspections in fresh apply | 23 | 1 |

Provider execution includes external installation and provider-local checks; it
is not an isolated measurement of downloads or installation. The serial totals
above do not overlap worker execution. On parallel runs, cumulative provider
durations must not be summed as wall time. Network, package availability and
runner variance affect the fresh-install comparison: execution actually became
slower in the Python 3.9 run, while inspection became substantially faster.

`--timings` measures provider validation, inspection, planning, fact gathering
and execution, plus invocation elapsed time. It does not isolate individual child
processes, graph/ownership work, configuration loading or CPU versus I/O time.
The structural costs below are source-derived hypotheses unless explicitly
marked measured. Windows and website runtime were not benchmarked for this review.

## Code-only pass

These changes preserve observable behavior, ordering, validation and failure
semantics. They do not extend provider plan reuse or change module configuration.

| Change | Repeated work removed | Why the code remains straightforward |
| --- | --- | --- |
| Cache topological order on each `ActionGraph` | Multiple full sorts of an unchanged snapshot, including deferred-condition proofs and scheduler queries | One optional immutable tuple; `add` and `connect` invalidate it. A newly introduced cycle is still detected. |
| Precompute retained/frozen module names during planning | Repeated scans of retained action IDs for every module | Local sets express exactly the membership question. |
| Use sets for completed/running membership | Linear tuple/list searches inside validation and scheduler loops | Preserve the original ordered completion loop; use a separate set only for membership. |
| Convert Homebrew inventory to sets for membership tests | Scanning an inventory tuple for every requested package | Requested package order and returned descriptions remain unchanged. |

A controlled graph benchmark constructed 2,000 nodes in a chain and requested
its order 200 times: **0.442852s before, 0.002402s after**. This intentionally
amplifies repeated graph queries. It is not a predicted speedup for dotfiles,
and does not imply minutes of remaining Python overhead. Regression tests cover
cache reuse, empty graphs, mutation invalidation and cycles after caching.

## Where time goes, and why

### 1. Package and extension execution — measured, highest fresh-run cost

Sources: [Homebrew action](../plugins/homebrew/action.py),
[VS Code action](../plugins/vscode/action.py).

The baseline macOS report attributed 106–117s to developer-tools Homebrew,
78–114s to personal-apps Homebrew and 60–66s to VS Code extension execution.
After inspection optimization, roughly 379–389s of fresh apply remains in
provider execution. Python loop tuning cannot eliminate this external work.

Etch installs only missing requested items and checks the result. Homebrew
batches requested packages within an action; VS Code reconciles extensions
sequentially and rereads inventory after each install. This avoids duplicate
work when an extension installs dependencies, and catches a successful exit
that did not establish the requested state.

Options and tradeoffs:

- Overlap independent execution with existing `--jobs 2`. This can overlap VS
  Code or scripts with Homebrew when dependencies and fact conflicts permit.
  It increases system/network load and makes timing less predictable. Homebrew
  operations must retain their shared lock.
- Batch across module boundaries. Fewer CLI startups could help, but combining
  actions complicates dependency gates, attribution, partial failure and refresh
  points. Do not merge unrelated modules merely to save startup time.
- Reduce extension verification frequency or batch installation. This needs
  explicit failure/partial-success and dependency tests; fewer inventory reads
  can mean redundant installs or delayed detection of a missing extension.
- Cache downloaded assets in CI. This can reduce download time on later runs,
  but is CI-specific, requires sound cache keys and does not make a genuinely
  fresh machine fast. Cache downloads rather than blindly restoring installed
  package state or privileged destinations.

Recommendation: measure child-command time inside these providers before
changing batching or post-install verification. Try a bounded parallel CI run
as a separate experiment; do not loosen the package-manager lock.

### 2. Inventory observation — measured, remaining no-op cost

Sources: [Homebrew CLI](../plugins/homebrew/cli.py),
[VS Code CLI](../plugins/vscode/cli.py),
[planning snapshot](../etchlib/planning/build.py).

Inventories require external CLI startup even when nothing needs changing.
Matching action inventories now share immutable results within a snapshot;
execution always reads current inventory. VS Code keys distinguish profiles,
and Homebrew distinguishes package types. The current warm repeat applies take
about three seconds; initial plans still take roughly seven to nine seconds.
Those cold-versus-warm observations alone do not prove a particular startup cause.

Why keep the reads: a new invocation must detect changes made outside Etch.
Persisting results across invocations makes no-op runs faster at the expense of
correctness unless tool-specific invalidation is reliable. Parsing private
Homebrew/VS Code storage could avoid CLI startup but couples Etch to internal
formats and platform details. A long-lived daemon adds lifecycle and invalidation
complexity to a dependency-free command-line tool.

Recommendation: retain snapshot-local sharing. Investigate cold subprocess
startup only if users still experience consistently slow initial plans; avoid a
persistent cache or daemon without stronger evidence.

### 3. Links, submodules and filesystem preflight — measured savings, deliberate checks

Sources: [link provider](../etchlib/providers/filesystem/link.py),
[submodule checks](../etchlib/providers/filesystem/submodules.py),
[create provider](../etchlib/providers/filesystem/create.py).

Repeated Oh My Zsh link inspection previously cost 17–24s during fresh apply.
It now runs once, taking about 0.8s in that run. Some linked directories require
Git subprocesses to prove their submodules are initialized at the recorded pins.
Execution still checks sources, parents, pins and destination conflicts before
mutation; the link provider preflights the batch before writing any destination.

These checks prevent linking an incomplete tree, escaping source ownership or
replacing a file introduced after planning. Source aliases retain inspection
because another action can retarget them. Cleanup retains discovery because its
candidate list and ownership proofs are not merely stable creation intent.

A repository-wide submodule snapshot could replace per-source subprocesses,
but it must preserve which source subtree is being linked and must be refreshed
when Git state can change. Reusing inspection inside one link apply could save
duplicate checks, but widens the interval between validation and mutation.
Skipping checks entirely changes safety behavior.

Recommendation: keep current mutation checks. If Git subprocess time becomes
material again, measure it separately and consider bounded source-tree sharing,
not a process-wide assumption that submodules never change.

### 4. Planning, deferred gates and graph proofs — structural scaling cost

Sources: [planner](../etchlib/planning/build.py),
[graph](../etchlib/graph/dag.py),
[execution validation](../etchlib/execution/validation.py).

A provider can change eligibility through refreshed facts. Rebuilding a graph
also catches newly active dependency cycles, privilege requests and conflicts
before they execute. The engine therefore still rebuilds after actual execution,
although opted-in provider intent can be retained and skipped actions do not
cause a rebuild.

Repeated topological sorting is removed by the code pass. Ancestor traversals
and completed-action history validation can still repeat as a repository grows.
Storing every ancestor set may accelerate repeated queries but can consume
quadratic memory on long chains. A fully incremental planner needs correct
invalidation for gates, refresh evidence, claims and already-started work; an
incorrect omission can authorize work under an invalid dependency history.

Recommendation: retain fresh graph proofs. Profile larger synthetic consumer
sizes before adding ancestor caches or incremental graph maintenance. Prefer
snapshot-scoped memoization with explicit bounds to permanent global indexes.

### 5. Ownership and cleanup — structural, safety-dominated

Sources: [claim validation](../etchlib/ownership/claims.py),
[cleanup](../etchlib/providers/filesystem/clean.py),
[receipts](../etchlib/providers/filesystem/receipts.py).

Claim checking compares each active claim with preceding claims and lexical/
resolved paths. It is quadratic in claim count, with filesystem resolution and
parent checks. This deliberately detects exact, ancestor and symlink-alias
collisions, including ownership of satisfied actions. Cleanup checks receipt
identity before deletion and again immediately before removal.

A path trie or sorted ancestor index could reduce comparisons, but must preserve
shared-directory exceptions, multiple normalized identities and platform-specific
path behavior. Caching normalized paths across execution can miss changed
symlink parents. Removing receipt reads would weaken deletion authorization.

Recommendation: do not change this for typical small configurations without a
claim-count benchmark. At large scale, prototype an index against the current
implementation as an oracle and retain adversarial alias/parent tests.

### 6. Fact storage, copies and repeated schema validation — structural, modest until large data

Sources: [fact store](../etchlib/facts/store.py),
[provider context](../etchlib/planning/context.py),
[condition evaluator](../etchlib/conditions/evaluator.py).

Facts are lazy and remain cached until explicit invalidation. Values/defaults
are copied so a provider cannot mutate another action's observations or consumer
configuration. Conditions and provider results are checked at boundaries, even
when earlier stages also validated declarations.

Large inventory values, deeply nested defaults or many actions can make copying
and repeated validation expensive. Sharing references is cheaper but changes
mutation isolation. Frozen dataclasses alone do not make nested lists/dicts
immutable. Prevalidated schemas or immutable observation types could reduce
copies, but introduce lifecycle rules and compatibility obligations for plugins.

Recommendation: benchmark realistic large values before weakening isolation.
Keep external probes lazy and refresh specific facts; avoid eager gathering in
ordinary plan/apply merely for convenience.

### 7. Parallel scheduling and resource locks — intentional throughput limits

Sources: [scheduler](../etchlib/scheduling/engine.py),
[observation compatibility](../etchlib/scheduling/observations.py),
[resource capacities](../etchlib/scheduling/resources.py).

Execution defaults to one job. Parallel dispatch repeatedly checks predecessors,
read/write conflicts and resource availability. Homebrew shares a single resource;
interactive input/elevation also serialize. These limits prevent package-manager
races, stale decisions and concurrent prompts.

More jobs improve only independent work; long serial dependencies remain the
critical path. Increasing a package-manager capacity is not equivalent to safe
parallel downloads. Scheduling indexes can reduce Python work at large scale,
but add invalidation and memory cost. Completion order and fail-fast behavior
must stay deterministic enough for users to understand partial results.

Recommendation: test two jobs on representative disposable consumers before
changing defaults. Retain shared mutation locks; measure resource-wait time if
we need to distinguish scheduling delay from active provider execution.

### 8. Scripts, installers, downloads and platform commands — bounded external waits

Sources: [command runtime](../etchlib/providers/commands/runtime.py),
[installer](../etchlib/providers/installer/provider.py),
[download transfer](../etchlib/providers/download/transfer.py),
[version probes](../etchlib/facts/version.py).

Arbitrary consumer scripts can legitimately take most of a run. Runtime commands
have configurable deadlines; the general command default is 300s and version
probes default to 10s. Installers/downloads use bounded transfers, byte limits,
TLS and optional hashes. Hidden command output is retained on disk for failure
diagnostics rather than held indefinitely in memory.

Lower timeouts fail faster but interrupt legitimate work and can leave partial
state. Retrying a mutating script automatically risks doing it twice. Persistent
HTTP connections or wider download concurrency can reduce latency but add
session/authentication/resource management. Dropping verification weakens
reproducibility and failure detection rather than optimizing equivalent work.

Recommendation: keep configurable bounds and fail-fast behavior. Measure child
commands, transfers and output size when provider execution is the dominant cost;
do not infer that all script time is engine overhead.

### 9. Preferences and Windows-specific operations — structural, not benchmarked here

Sources: [macOS preferences](../plugins/macos_defaults/action.py),
[Windows Registry](../plugins/windows_registry/action.py),
[Windows invocation](../etchlib/providers/commands/windows.py).

macOS reads each domain and writes changed keys through separate `defaults`
processes. This preserves unrelated preferences and native type handling.
Windows Registry uses native access; PowerShell commands add process startup and
must retain the selected compatibility/interpreter behavior. These providers
still receive ordinary inspection rather than reusable intent.

Bulk preference replacement can reduce subprocesses but can lose unrelated keys
or race other applications. A persistent PowerShell session reduces startup but
introduces environment/state leakage and lifecycle handling. Reusable preference
intent is a candidate only after reviewing its current-state checks and tests.

Recommendation: measure actual domain/key or PowerShell counts first. Avoid
whole-domain replacement or interpreter changes as a performance shortcut.

### 10. Configuration, validation, formatting and plugin loading — startup and tooling costs

Sources: [configuration](../etchlib/config.py),
[validation](../etchlib/config_validate.py),
[formatter](../etchlib/config_format.py),
[plugin loading](../etchlib/plugins/loader.py).

Literal parsing, duplicate-key/schema checks, module discovery and plugin imports
cost startup time proportional to configuration size. Validation loads each
profile, which repeats configuration work. The formatter tokenizes comments,
walks literals and reparses output to prove semantic preservation; comment lookup
scans may become costly in very large files.

These choices avoid executable configuration and preserve human comments and
format semantics. Reusing parsed declarations across profiles or indexing comment
positions could help large repositories, but must preserve independent selection,
error order and formatting output. Persisted parsed files need invalidation for
configuration, plugin and schema changes.

Recommendation: keep parsing local and dependency-free. Benchmark many profiles
or large comment-heavy files before adding caches. CLI doctor also performs a
repository submodule check before loading code, then diagnosis checks setup again;
that duplication is a separate candidate, not removed by this code-only pass.
The pre-load check exists to surface missing modules before configuration fails.

### 11. Import and submodule update — intentionally explicit acquisition cost

Sources: [Git acquisition](../etchlib/importing/git.py),
[tree materialization](../etchlib/importing/tree.py),
[submodule update](../etchlib/submodules.py).

Import uses an isolated Git repository, validates tree metadata and limits files/
bytes. It already batches blob requests and extraction, avoiding one network
request per file. Filter fallback can fetch more than desired when a server does
not support partial acquisition. Git acquisition has a shared 120s deadline.
Submodule update delegates to Git and intentionally allows normal interactive
Git execution without imposing an arbitrary installation-length timeout.

Cross-import object caches could save network work but introduce trust,
authentication, provenance and eviction decisions. More parallel Git operations
increase load and can complicate error attribution. Automatically advancing pins
would change reproducibility, not merely make the same operation faster.

Recommendation: preserve selective batching, bounded import validation and
explicit pin updates. Optimize acquisition only with measured repeated imports;
these commands are outside ordinary apply's critical path.

### 12. Website and project CI — separate from consumer apply

Sources: [website package scripts](../website/package.json),
[website workflow](../.github/workflows/website.yml),
[project workflow](../.github/workflows/project.yml).

Website quality work includes separate lint/type jobs, coverage, an Astro build,
three browser engines and Lighthouse. CI already shares build artifacts between
validation/browser/Lighthouse jobs, and tests run in parallel. Social-card
regeneration uses a browser only when explicitly requested, not on every build.
Core CI tests multiple Python/OS environments, template consumption and source
release behavior. Setup/install overhead repeats across isolated jobs.

This buys independent failures, portability, accessibility and release confidence.
Combining jobs saves setup and runner minutes but may reduce parallel feedback
and failure isolation. Reducing the browser/OS matrix shortens CI at the expense
of compatibility coverage. More CI caching needs platform/tool/lockfile keys.
Static website build work does not slow the Etch CLI; do not conflate those costs.

Recommendation: inspect job critical paths and runner minutes separately before
changing gates. Keep browser/build artifact reuse and scoped workflows. Website
and CI were reviewed structurally, not timed by this investigation.

## Suggested next decisions

1. Keep the measured provider optimizations and this small code-only pass. They
   achieve ordinary warm apply in a handful of seconds without a persistent cache.
2. Trial existing bounded parallel execution in a disposable consumer, with
   provider and resource-wait evidence, before changing execution defaults.
3. If fresh installation remains the concern, add child-command timings for
   Homebrew and VS Code and then evaluate startup/batching/verification costs.
4. If large configurations are the concern, benchmark graph ancestors, ownership
   claims, copies, profile loading and comment indexing at increasing sizes.
5. Leave destructive validation, receipt proofs, alias handling, mutation locks
   and transfer verification intact unless a replacement proves equivalent safety.

There is no evidence that a runtime dependency, daemon, OS factory refactor or
persistent inventory cache is needed to solve the observed performance problem.
