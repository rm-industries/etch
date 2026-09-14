# Conditions

Conditions select module and action behavior using observations. The evaluator
returns TRUE, FALSE or DEFERRED; a result cannot be implicitly converted to a
Python boolean. Inspect `result.outcome` explicitly so deferred work is not dropped.
This API supports the forthcoming graph/planner; it does not execute actions.

## Vocabulary

```python
{"os": ["linux", "macos"]}
{"os": "linux", "distro": "ubuntu", "arch": "x86_64"}
{"command": "git"}
{"env": "CI"}
{"env": {"name": "CI", "equals": "true"}}
{"fact": {"name": "tmux_version", "matches": ">=2.1,<4"}}
{"fact": {"name": "enabled", "equals": True}}
{"not": {"command": "starship"}}
```

Dictionary keys are AND. List values are OR alternatives for that key, including
lists of fact predicates. `not` takes a condition dictionary, not a list. Empty
conditions, empty alternatives, unknown keys and invalid predicate shapes fail
validation before any probe. Version constraint syntax is validated even if the
branch would not apply.

Platform predicates compare exact strings to the global facts. Command predicates
test executable presence. An environment name tests whether it is set, including
an empty value; `{name, equals}` compares its string value. Absent commands,
environment variables or unavailable platform properties return FALSE.

Fact predicates resolve names only in the evaluator's module. `{name}` requires
a boolean fact; `{name, equals}` compares value and type (True does not equal 1).
`{name, matches}` uses the [version comparison grammar](versions.md). Supplying both
comparators is invalid. Missing declarations, probe ERROR states and inappropriate
value types raise `ConditionError` with context.

## Deferral and refresh

Required named facts are different from presence checks: an unavailable version
must not silently choose a branch. `Evaluator(store, context, earlier_refresh=...)`
accepts an optional mapping from scoped `FactRef` to an earlier producer's identifier.
With such evidence, unavailable facts return DEFERRED and record the waiting facts
and producer descriptions. Without it, unresolved required observations raise an
actionable error. Merely declaring a fact or refresh target does not enable deferral.

The caller must provide only producer paths validated as eligible and earlier for
this consumer. The evaluator does not infer ordering or treat every installer as
eligible. Establishing that evidence against the DAG belongs to #11. Once a producer
has run, invalidate the affected observations, remove it from pending evidence and
reevaluate. A producer that still leaves a required fact unavailable then yields an
unresolved error rather than endless deferral.

A stale fact with a pending producer stays deferred until that producer finishes.
Without a pending producer, the store refreshes stale observations before evaluation.
Fact inputs remain scoped and cached; inline command/environment checks inspect
current state on each evaluation.

`not DEFERRED` remains DEFERRED. FALSE dominates an AND; TRUE dominates an OR.
An unavailable named fact that proves irrelevant to the final boolean result does
not cause an unresolved error or retain a waiting reference. Evaluation short-circuits
in declaration order. Actual ERROR observations encountered during evaluation remain
errors; they are not downgraded to absent or deferred observations.

## Module and action gates

`select_module(module, evaluator)` validates the module/action condition syntax,
evaluates the module gate first, and returns ordered action results. The evaluator
must belong to that module. A FALSE module gate skips action observations; a
DEFERRED module gate keeps every action deferred with the module's waiting facts.
With a TRUE module gate, action conditions evaluate individually; absent gates are
TRUE. These results do not replace provider schema, ownership or dependency validation
when an action becomes active.

Schema validation, result types, predicate evaluation and module/action selection
are separate files under `etchlib/conditions/`. Graph integration, plan/apply CLI and
execution remain separate roadmap issues.
