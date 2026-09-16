# Resource-aware scheduling

`etch apply --jobs 4` permits up to four independent actions at once. The default
is one job. `--jobs 1` explicitly restores serial execution. Configure a consumer's
default in `defaults.conf`:

```python
{
    "schema_version": 1,
    "execution": {
        "jobs": 4,
        "resources": {
            "package-manager:brew": 1,
            "application:vscode": 1,
            "network": 2,
        },
    },
}
```

`jobs` is an integer from 1 to 64; the CLI overrides the configured job count.
Resource capacities are positive integers. Unconfigured resources have capacity
one, including package-manager resources. A resource name starts with a lowercase
letter and contains lowercase letters, digits, dots, underscores or hyphens. It
may have one colon followed by a nonempty suffix starting with a letter or digit,
for example `package-manager:brew` or `application:vscode`.

Providers request one slot in every resource listed in `Plan.resources`. Duplicate
names count once. The coordinator reserves the whole set atomically; an action
never holds one reservation while waiting for another. Unrelated actions can pass
a resource-blocked action. Provider names do not affect scheduling. A `network`
flag reports behavior; a `network` resource is a separate capacity request.

## Readiness, ordering, and privilege

An action starts only after all of its action ancestors complete successfully.
Actions within a module remain ordered. Module dependencies wait for all relevant
actions in the prerequisite module. Stable graph order breaks ties among ready
candidates; completion timing does not override dependencies or reservations.
Results are displayed in dispatch order, followed by skipped/blocked work.

`sudo-interactive`, `stdin-interactive`, and `terminal` are reserved capacity-one
resources. Either interactive resource also reserves `terminal`, preventing a
sudo prompt from racing with another action reading stdin. Elevated plans acquire
`sudo-interactive` even if a provider omits it from its resource list. `--allow-sudo`
is still required; additional jobs do not grant privilege. Other resource capacities
can be raised only when the underlying tool supports concurrent mutations.

## Facts and staged validation

The coordinator owns the fact store. After a successful action returns, it marks
only declared refresh facts stale, then rebuilds eligible pending work. A worker
gets its own detached, read-only mapping of already gathered observations; it
cannot trigger a concurrent gather through that context.

Consumers of a fact do not overlap an in-flight refresher of that fact, and two
refreshers of the same fact do not overlap. Reads include named condition facts,
`Plan.facts`, and context facts requested during provider inspection. Declare
explicit dependencies when a consumer must observe a particular producer: a shared
fact access constraint alone does not express a required direction of execution.

Pending work whose predecessors are unfinished keeps its previous snapshot and
cannot start. Inspection of actions sharing a resource with running work is also
postponed. Newly activated work whose resources or fact inputs are not known yet
waits until in-flight resource holders and fact writers have completed before
inspection. This conservative rule avoids observing partially mutated state while
constraints are being discovered. Independent actions without those conflicts keep
running, and a refreshed branch can configure while unrelated long-running work
continues. Reservations are not a substitute for truthful provider metadata:
opaque scripts and undeclared side effects cannot be inferred by the scheduler.

Completed and in-flight actions retain their plans and ownership claims during
replanning. New activation cannot insert a prerequisite before an action that has
already started. Newly active providers, claims, dependencies, fact references and
privilege requests still go through normal validation before dispatch.

## Failures and provider requirements

On the first observed failure, no new actions are dispatched. Already running
mutations are drained and their outcomes are retained, including selective refresh
for successful returns. Failed dependents remain blocked. No automatic retry,
rollback, or cancellation of a running provider is attempted. For strict serial
failure behavior, use one job.

A registered provider instance may receive concurrent calls when multiple jobs are
enabled. Keep state local to each call, avoid process-wide environment/cwd changes,
and declare resources for unsafe shared operations. Planning calls are serialized
on the coordinator but may overlap independent application calls. Provider-owned
resources and fact metadata must accurately describe those interactions. Locks
coordinate only this Etch invocation, not other Etch or package-manager processes.

The implementation separates resource validation/reservations, observation guards,
worker calls, and coordination under `etchlib/scheduling/`. Execution results keep
the same records and CLI statuses as serial application.
