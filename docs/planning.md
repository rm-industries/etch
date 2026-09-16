# Planning changes

Run from a consumer repository, or supply its root:

```sh
./etch plan --repo examples/minimal --profile developer
./etch plan --repo examples/minimal git --verbose
```

As with `doctor`, choose either a profile or explicit module names. With neither,
Etch selects every discovered module in lexical order. Profile order is retained
where dependencies permit. Required modules must be selected explicitly.

The output includes:

- Selected modules, false-condition skips and deferred actions.
- A stable dependency order, current provider observations and proposed
  `CHANGE`, `RUN` or `SKIP` outcomes.
- Configured job limits and resource capacities, refresh points, resource constraints,
  elevation requests, and known network
  and executable behavior. Opaque actions may do more than Etch can predict.
- Active destination ownership, with conflicts reported as errors.
- Requested fact values and unavailable observations. Unused declarations remain
  unprobed and are labeled `not requested`.
- Plugin compatibility; `--verbose` also lists core and plugin provider origins
  and versions, including fact providers.

Planning returns zero for a valid snapshot, including valid deferred work. Invalid
configuration, provider errors, unresolved required facts, missing hard dependencies,
cycles and ownership conflicts return one and a diagnostic on stderr. Missing soft
`after` targets produce warnings. `doctor` retains its structural-only behavior.

## What inspection means

Planning calls provider validation, inspection and planning methods. It never calls
an action provider's `apply`, downloads an installer, or executes a shell/script
**action**. Core inspection reads paths, environment variables and command presence.
Requested version facts may run their bounded argv probes. Choose version probes
that only inspect the system. Their configured commands are executable code.

Declared plugins are trusted Python, including import-time code and inspection
methods; planning does not sandbox them. A provider must honor the read-only
inspection contract. No elevation is granted by planning. A plan may report that
an action will need elevation when application is implemented.

The report prints requested fact values, so avoid sharing output containing private
environment facts. Provider payloads and command environment dictionaries are not
printed. Plans describe known executables but cannot predict arbitrary script effects.
For opaque commands, a missing network declaration is reported as `unknown`.

## Deferred work

An unavailable named fact initially leaves its condition unresolved. The planner
inspects enabled actions and builds a dependency graph, then checks whether an
eligible earlier action refreshes that fact. A producer must be enabled, propose
actual work, and have only enabled ancestors. A skipped, self, later or unrelated
producer cannot justify deferral. Unresolved conditions without that evidence fail.

For example, an installer action with `"refresh": ["tool_version"]` can precede
an action gated by `"when": {"fact": {"name": "tool_version", "matches": ">=1"}}`.
If the tool is absent, the second action is shown as deferred without inspecting
its provider or claiming its destinations. The installer is not downloaded.

This is a snapshot of current observations. Refresh entries describe future work;
planning neither invalidates nor regathers facts after proposed changes. Deferred
actions need new condition evaluation, provider inspection, dependency validation
and ownership checks after the producer succeeds. The [staged executor](applying.md)
performs those checks during `apply`. The existing graph rules withhold dependencies attached to
inactive/deferred gates; declaring a dependency on an unresolved action does not
by itself prove an earlier producer.

## Internal API

`etchlib.planning.build.plan_repository(repository, registry)` returns a `Report`
containing selections, the graph, observations, provider plans, facts and validated
claims. Providers receive a lazy read-only fact mapping: accessing a declared fact
requests its cached, detached observation. A plan's `facts` metadata also requests
those observations. The text renderer operates on the completed report and does
not perform further inspection.
