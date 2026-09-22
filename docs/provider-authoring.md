# Authoring providers

Providers implement capabilities; plugins package and distribute them. Start with
an existing provider below rather than inventing a second execution framework.
Core and plugin providers use the same Python 3.9-compatible protocols, registry,
result records, planner and executor. Core and reference bundles use only the
standard library at runtime.

## Read the shipped implementations

| Example | What to learn | Implementation and executable checks |
| --- | --- | --- |
| `create` | Small complete lifecycle; shared directory claims; apply-time rechecks | [provider](../etchlib/providers/filesystem/create.py), [tests](../tests/test_filesystem_providers.py) |
| `link` | Module-owned assets, consumer destinations, explicit defaults, exclusive claims and receipts | [provider](../etchlib/providers/filesystem/link.py), [snapshot tests](../tests/test_filesystem_snapshot.py) |
| `installer` | Presence check, opaque/network metadata, bounded HTTPS retrieval only during apply | [provider](../etchlib/providers/installer/provider.py), [schema](../etchlib/providers/installer/schema.py), [execution tests](../tests/test_execution_installer.py) |
| `vscode` | External entrypoint, normalized extension inventory, missing-only application and facts | [bundle](../plugins/vscode/), [entrypoint](../plugins/vscode/etch_plugin.py), [fact/refresh tests](../tests/test_vscode_facts.py) |
| `brew` | Batched package reconciliation, explicit refresh and shared package-manager resource | [bundle](../plugins/homebrew/), [entrypoint](../plugins/homebrew/etch_plugin.py), [integration tests](../tests/test_brew_integration.py) |

These files are the maintained examples, not pseudocode copies. The reference
plugins currently live in this monorepo but remain explicitly loaded source
bundles; their location does not make their providers part of core.

## Follow the lifecycle

Implement `ActionProvider` structurally; inheritance is unnecessary. Use the
[protocol signatures](../etchlib/providers/contracts.py) and
[checked lifecycle helpers](../etchlib/providers/lifecycle.py).

1. `validate(config, context)` returns `None` or raises a useful error. Validate
   shapes and options without mutation or installer execution. Doctor can call
   it even for actions behind false/deferred conditions.
2. `inspect(config, context)` observes current state and returns an `Inspection`:
   SATISFIED, CHANGE or UNKNOWN, plus provider-owned data and an optional reason.
   Keep observations bounded and read-only; a version/list command may run here,
   but installation must not. Missing optional state and broken prerequisites are
   different cases: explain which one you observed.
3. `plan(config, observation, context)` returns a `Plan` with SKIP, CHANGE or RUN,
   a useful description, payload and complete scheduling metadata. SKIP still
   owns its declared paths. UNKNOWN/opaque work is not proof of a needed change.
4. `apply(plan, context)` performs the intended mutation and returns
   `ApplyResult(changed, description)`. Recheck assumptions that can change after
   planning; never rely on a stale executable path, destination parent or package
   inventory. Report what happened, including unchanged results. Do not retry or
   invent rollback: partial progress may remain on failure.

Exceptions receive provider origin and lifecycle-phase context. The executor
validates the graph, ownership, resource and privilege rules before dispatch and
replans after refresh. A provider must not call another provider's apply method
or create its own scheduler to bypass those checks.

This complete snippet exercises the real `create` provider in a temporary directory
and can run from an Etch checkout with `python3 -S`. Direct lifecycle calls are
appropriate for an isolated provider check like this; use `apply_repository` or
the CLI for real multi-action configuration.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from etchlib.core import core_registry
from etchlib.providers.contracts import Context
from etchlib.providers.lifecycle import apply_action, inspect_action
from etchlib.providers.plans import PlanStatus

with TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    context = Context(root, root, "example", {})
    entry = core_registry().action("create")
    _, plan = inspect_action(entry, ["config"], context)
    assert plan.status is PlanStatus.CHANGE
    assert not (root / "config").exists()
    assert apply_action(entry, plan, context).changed
    _, second = inspect_action(entry, ["config"], context)
    assert second.status is PlanStatus.SKIP
```

`Context` gives the consumer root, owning module root/name, declared fact
observations, provider defaults and execution-time elevation authorization.
Treat all inputs as read-only. Frozen records do not recursively freeze their
payloads. Keep mutable state call-local: one provider instance can serve multiple
worker threads, and inspection can overlap unrelated application. Avoid changing
process cwd, PATH or environment; pass subprocess arguments/cwd/env explicitly.

## Defaults, assets and ownership

Defaults are opt-in. Normalize with `compose_defaults`, listing the exact keys
supported by the provider; action options replace individual defaults atomically.
There is no recursive merge. Fact declarations do not automatically inherit action
defaults: supply their command/profile options separately when needed.

Use `Module.asset()` for module-owned input files and `destination()` for consumer
output paths. The former confines resolved assets to the module root; the latter
expands `~` and anchors relative destinations at the consumer root. Do not confuse
these namespaces or implement a second path resolver.

`create` uses SHARED_DIRECTORY claims so other actions may own child paths. `link`
uses EXCLUSIVE claims for managed destinations and records its ownership for
later clean operations. Include claims even when already satisfied. Same-path or
ancestor conflicts are rejected according to claim kind, including aliases through
resolved parents. Revalidate before mutation; a successful earlier plan is not a
permanent guarantee about the filesystem. See [ownership](ownership.md).

## Facts and explicit refresh

A `FactProvider` implements `validate` and `gather`. Return VALUE for a known value,
UNAVAILABLE for a missing observation, or ERROR for a failed probe, with reasons
for the latter two. A VALUE may legitimately contain `None`. STALE belongs to the
store's invalidation lifecycle: returning it from a fresh probe is treated as ERROR.

`FactRef(module_name, local_name)` identifies a declared module fact; `None` as the
module identifies a global built-in. Equal local names in different modules are
independent. Consume facts through `context.facts` and declare inputs in
`Plan.facts`; inspection-time reads are also tracked. Workers receive detached
observations and cannot lazily gather undeclared or unobserved facts.

Declare affected facts in `Plan.refresh` or action-level `refresh`. Refresh happens
after successful apply, even if `changed` is false. Skipped or failed actions do
not refresh. Do not silently infer that installing a package proves a command or
version fact. Brew's inventory, core command/version probes and VS Code's inventory
remain separate observations with explicit declarations.

A missing fact can defer a condition only when the graph provides an eligible
earlier refresh producer. After the producer finishes, the engine gathers fresh
state and inspects newly active work. Still-unavailable required facts and newly
visible destination conflicts stop execution; completed changes are not rolled
back. See [facts](facts.md), [conditions](conditions.md), and
[staged application](applying.md).

## Dependencies, resources and execution flags

Use `Plan.requires` for required selected modules and `Plan.after` for optional
ordering; action/module metadata can declare these as well. A missing hard
requirement fails planning. An absent soft `after` target produces a warning.
Neither field selects modules, imports dependencies or installs a plugin. Cycles
are rejected before dispatch; the newly active graph is checked after refresh.

Use resource strings for shared mutable services that path claims cannot describe.
Homebrew declares `package-manager:brew`; VS Code declares `application:vscode`.
Unconfigured resources have capacity one. Declare the entire resource set before
apply; the coordinator reserves it together rather than letting workers partially
acquire locks. Resources serialize work within this Etch invocation, not unrelated
external processes or another Etch process. See [scheduling](scheduling.md) for
capacity configuration and fact read/write coordination.

Set `network` when work needs network access, `opaque` when Etch cannot determine
its complete effects, and `elevated` when it needs authorized privilege. Interactive
plans share terminal resources; do not use background workers to bypass stdin or
sudo serialization. Authorization is separate from declaring elevation. The
installer implementation demonstrates these flags and checks authorization before
execution. No action-level retry, rollback or global transaction is implied.

## Consumer configuration examples

These are action dictionaries to place in a module's `actions` list. They use
Python literal syntax supported by configuration schema 1 and Python 3.9. Paths,
prerequisites and referenced facts must be supplied in the owning consumer.

```python
{"create": ["~/.config/example"]}
{"link": {"~/.config/example/settings": {
    "path": "files/settings", "create": True
}}}
{"installer": {
    "url": "https://example.invalid/install-tool",
    "check": {"command": "example-tool"}
}, "refresh": ["tool_version"]}
{"vscode": {"extensions": ["editorconfig.editorconfig"]}}
{"brew": {"formulae": ["git", "tmux"]}}
```

The installer URL is deliberately nonfunctional. Review and choose a real
installer in the consumer, then declare `tool_version` there, for example:

```python
{"facts": {"tool_version": {
    "version": {"command": ["example-tool", "--version"]}
}}}
```

The latter is a module field fragment, not a standalone configuration file.
A complete module also requires `schema_version` and `name`. Neither plugin is
available until its bundle is explicitly declared. `code` and `brew` must already
be available for their providers to inspect. Their complete configuration and fact
examples are in the [VS Code](../plugins/vscode/README.md) and
[Homebrew](../plugins/homebrew/README.md) bundle READMEs. Both implement presence
reconciliation rather than upgrading/removing unrelated installed state.

## Package and load explicitly

Use an `etch_plugin.py` entrypoint with exact `PLUGIN` metadata and both factories,
even when one returns no providers. Keep implementations in focused sibling files
and import them relatively. Use the reference entrypoints above as typed examples.

For a vendored bundle, declare this in consumer `defaults.conf`:

```python
{"schema_version": 1, "plugins": ["vendor/etch-example"]}
```

A local development checkout can instead use an explicitly configured absolute
path. A Git submodule uses the same relative declaration after initialization;
its gitlink pins the bundle revision independently of the engine. Runtime loading
needs only the source files, not Git or network. No root scanning, installed-package
discovery, implicit dependency installation or hot reload is provided. Plugin code
is trusted executable Python: even metadata validation occurs after entrypoint
execution. Read [loading and failure behavior](plugins.md) before distribution.

Keep these axes separate:

| Axis | Meaning |
| --- | --- |
| Engine release/revision | The Etch implementation pinned by the consumer |
| Plugin release/revision | The bundle implementation pinned independently |
| `PLUGIN["api"]` | Integer provider/plugin API compatibility; must equal the engine's supported API |
| Configuration `schema_version` | Literal configuration format, independent of plugin release numbering |

Release strings are informational; the loader does not solve version ranges or
certify every provider behavior from an API match. Test each supported engine/API
combination. Keep Python 3.9 syntax and standard-library runtime imports in official
bundles; use isolated subprocesses/fake tools for bounded provider verification.
The engine matrix exercises the reference implementations on Linux/macOS.

## Promote a provider into core without renaming configuration

Promotion changes distribution, not the consumer-facing provider name, payload,
fact names or lifecycle behavior. First establish compatibility through the same
provider tests. If those contracts must change, treat that as a separate breaking
change instead of calling it a distribution-only promotion.

For consumers, migrate explicitly:

1. Pin an engine release that contains the promoted provider.
2. Remove the old plugin declaration if it supplied only the promoted providers.
   If it also supplies other providers, pin a compatible plugin release that omits
   the promoted names while retaining the rest. If no such release exists, defer
   the upgrade or split the bundle first.
3. Keep module action/fact configuration unchanged. Review `doctor` and `plan`:
   origin should change from plugin to core without changing the desired behavior.
4. Validate apply and the next declarative no-op, then remove unused vendored files
   or submodule pins as an explicit consumer maintenance change.

Never register both versions and rely on order to choose one. Names are unique
across action and fact providers; duplicate names, including attempted core
shadowing, fail registration. There is no override, alias or silent fallback. The
loader's rollback protects its registry changes, not side effects of executing
untrusted plugin code. This is a documented migration procedure, not automatic
promotion/update behavior in the engine.
