# Provider contracts

Providers implement capabilities; plugins distribute providers. Core and external
implementations register through the same `Registry`. This API is provisional
while the engine and first integrations are built.

## Files and responsibilities

| Module under `etchlib/providers/` | Responsibility |
| --- | --- |
| `contracts.py` | Action/fact protocols and execution context |
| `observations.py` | Inspection results, scoped fact references and fact states |
| `plans.py` | Plans, path claims and apply results |
| `registry.py` | Registration, lookup and origin metadata |
| `lifecycle.py` | Validated inspection/planning and fact gathering |
| `errors.py` | Provider-boundary diagnostics |

## Registration

```python
from etchlib.providers.registry import Origin, Registry

registry = Registry()
# Implementations are instantiated by core or the explicit plugin loader.
registry.register(Origin("etch-example", "0.1.0"),
                  actions=[example_action], facts=[example_fact])
entry = registry.action("example")
```

Names are unique across the entire active registry, including action/fact kinds.
They start with a lowercase letter and may contain lowercase letters, digits,
underscores, hyphens and dots. Dots are literal identifier characters, not namespace
or alias resolution. Action names cannot collide with action metadata keys.
Duplicate names never override an existing provider, including a core provider.
Lookup of a missing name or the wrong capability kind fails explicitly.

Registration checks required callable methods and commits the whole bundle only
after every entry passes. It preserves registration order and records each entry's
origin name, version and core flag. It does not invoke validate, inspect, plan,
gather or apply. Signature/type checking by static tools and runtime result checks
complement callable checks; registration alone cannot prove provider correctness.

## Lifecycle

Action providers implement `validate`, `inspect`, `plan` and `apply`. Fact providers
implement `validate` and `gather`. No inheritance is required. `validate` returns
`None` or raises an exception. The shared helpers attach provider/method context
to failures and reject untyped inspection, plan and fact results.

`plan_action(entry, config, context)` validates, inspects and plans, without calling
apply. Plans carry module dependencies (`requires` and `after`), scoped fact inputs,
filesystem claims, refresh references, execution resources, privilege requests,
known network use and opaque-side-effect flags. Provider code must accurately
declare these constraints. A successful plan is not permission to execute it:
the future engine must validate dependency, ownership and privilege constraints
before invoking `apply`. The apply contract returns an `ApplyResult`; this change
does not add an executor or an apply CLI.

`gather_fact` validates and returns VALUE, UNAVAILABLE, STALE or ERROR observations.
UNAVAILABLE and ERROR require explanations and cannot contain values. VALUE may
legitimately contain `None`; STALE may retain an earlier observation. Fact references
use separate module/name fields, so identical local names in different modules
remain distinct. Caching, invalidation and selective refresh are subsequent work.

Records have frozen fields and plan metadata uses tuples. Provider-owned payloads,
observed values and the context's fact mapping are not recursively frozen; providers
must treat inputs as read-only and own any mutable output data they retain.

Providers can normalize dictionary options with
`etchlib.config.compose_defaults`, explicitly declaring which defaults they support.
Composition is atomic replacement, not recursive merging. Non-dictionary provider
payloads need provider-specific normalization; the registry does not assume a schema.

## Current scope

The tests run stateful core-origin and external-origin fixtures through the same
registration, validation, inspection, planning and explicit application interfaces.
These are test fixtures, not shipped core providers. Explicit plugin loading and
API compatibility checks are implemented; see [plugin loading](plugins.md).
Concrete providers, repository-wide preflight, scheduling and complete doctor
diagnostics remain in their own roadmap issues.
