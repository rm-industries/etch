---
title: "Applying a staged plan"
description: "Apply a fresh plan with explicit privilege, refresh, output and failure behavior."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Applying a staged plan

```sh
./etch plan --repo /path/to/dotfiles --profile developer
./etch apply --repo /path/to/dotfiles --profile developer
./etch apply --repo /path/to/dotfiles git zsh
```

Select either a profile or module names. With neither, all discovered modules are
selected. Dependencies do not implicitly select additional modules. `apply` builds
its own fresh plan; an earlier `plan` invocation does not authorize stale work.

The executor defaults to one job. Set `--jobs N` or configure `execution.jobs` to
run independent ready actions concurrently. It follows the validated dependency
graph and uses selection/declaration order to break ties. See
[resource scheduling](scheduling.md) for capacities, observation coordination and
provider concurrency requirements. Locks apply within this invocation, not across
Etch processes or external package managers.

## Establish, refresh, resolve, validate, configure

Before the first mutation, Etch validates current active providers, dependencies,
ownership and privilege requests. Every configured refresh name must identify a
declared fact, including names in inactive branches. Provider-derived refresh
references are checked when that provider is activated and planned.

After an action successfully returns an `ApplyResult`, only its declared refresh
facts are invalidated. Cached observations become `STALE`; unused facts remain
ungathered. The next consumer gathers a fresh observation. Facts outside that
refresh set retain their cached values. Etch does not refresh the whole process
environment or infer which programs a shell command may install.

Successful application invalidates declared facts even when the provider returns
`changed=False`: another process may have satisfied the action since inspection.
A `SKIP` plan is not applied and does not invalidate facts. A failed provider or
invalid return value does not trigger refresh.

Pending conditions are reevaluated after executed actions. Providers normally
receive fresh inspection, but may explicitly declare executable plans reusable
when apply reconciles current state and scheduling metadata stays valid. Those
plans are retained while their declared fact inputs remain unchanged; satisfied
and opaque plans are still re-inspected. Skips do not trigger a new snapshot.
A deferred condition may become true or false. Newly active work receives provider payload,
path, dependency/cycle, ownership, refresh and privilege validation before it can
run. An unavailable fact with no remaining eligible producer is a failure, even
if an installer reported success. No action stays silently deferred forever.

Completed actions never run twice in one invocation. Their validated plans and
ownership claims remain in subsequent snapshots, and claims are normalized again
against the filesystem. A module gate is fixed once its first active action has
completed. Pending action gates can still change after refresh. If activation
would insert a new prerequisite before already completed work, Etch stops with a
diagnostic; it cannot retroactively honor that dependency.

For example, declare `starship_version` using the `version` fact provider. An
installer action can declare `"refresh": ["starship_version"]`, followed by a
link action gated on that version. On a fresh machine the link remains deferred;
after installation, the version is observed and the link is validated and applied.
With an installer presence check and an already-correct link, a second apply skips
both actions without downloading the installer again.

## Privilege and trusted code

Elevation is disabled by default. `--allow-sudo` explicitly authorizes declared
privilege requests for that invocation, including actions activated after refresh.
The context passed to providers records that authorization; Etch itself does not
launch the whole run under sudo. Providers remain responsible for their own
privileged commands and operating-system authentication.

Plugins, shell commands, scripts, installers and version probes are executable
code. Review consumer configuration before applying it. Planning and application
both import declared plugins, and neither sandboxes their Python code.

## Results and failure policy

Apply output groups results by module and lists multiple link destinations on separate lines.
Conditional skips name the unmet requirement without printing observed values.

Every selected action receives one terminal status:

- `CHANGED`: the provider reported changes.
- `UNCHANGED`: application succeeded and reported no changes.
- `SKIPPED`: its condition was false or inspection produced a `SKIP` plan.
- `FAILED`: application failed or returned an invalid result.
- `BLOCKED`: a failed dependency chain or a run-level safety error prevented execution.

An action execution failure stops remaining actions in that module and blocks
transitive dependents through either `requires` or `after`, including action-level
and provider-derived dependencies. Blocked results identify the originating failed
action. This conservative policy treats ordering as an operational dependency on
success during apply, even though `after` remains optional during selection.
Independent modules continue in both serial and parallel runs. Sharing a resource
alone does not propagate failure; reservations are released when an action finishes.
Already running independent work is allowed to finish and its results are retained.

Configuration, graph, privilege and ownership errors still stop new dispatch, as
does interruption. A validation failure between actions is reported at run level;
no provider is falsely marked as having run. There is no rollback or generic retry.
A failed provider may partially mutate the system, so all cached observations are
invalidated and eligible pending work is reinspected before continuation. This is
not a successful refresh: the failed chain remains blocked. Retry behavior belongs
to individual providers, such as [opt-in VS Code retries](../plugins/vscode/README.md).

The summary retains every action failure and completed change. Fix the reported
problem and rerun apply; idempotent providers inspect real state and skip satisfied
work. Dependencies must be declared: Etch cannot infer relationships hidden in
scripts or external side effects.

The CLI returns zero only for a fully successful run, including legitimate skips.
Configuration, validation, application and interrupted-run failures return nonzero.
The Python API `apply_repository(repository, registry, allow_sudo=False, jobs=None)` returns
an `ExecutionReport` with ordered action results, observed fact states, warnings
and an optional error. Repository/fact registration errors can raise before a run
starts. Rendering is separate from execution.

## Measure provider work

Use `etch plan --timings` or `etch apply --timings` to append a timing report to
stderr without enabling verbose command output. Each module/provider/phase row
shows call count, cumulative duration and longest call, sorted by cumulative time.
Validation, inspection, planning, fact gathering and execution are measured;
execution time includes installations, downloads and external commands.

The header shows invocation elapsed time. Parallel provider durations overlap
and must not be added to estimate elapsed time. The report omits arguments,
configuration values and captured output; normal failure diagnostics still apply.
Timing collection is disabled by default and requires no extra dependencies.
Compare a fresh apply with a second apply on a disposable runner to distinguish
installation-heavy runs from repeated checks. Provider timings do not separately
measure each child command or all engine overhead.
