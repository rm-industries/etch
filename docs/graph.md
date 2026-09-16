# Action dependency graph

`build_graph(repository, selections, plans, fact_links)` constructs and validates
one graph snapshot without running providers. It consumes selected repository
modules, condition `Selection` results and optional normalized provider `Plan`s
keyed by `NodeId(module, "action", index)`. Rebuild after condition activation or
plan changes; a previous valid graph does not authorize newly activated work.

## Nodes and ordering

Each participating module has a start gate and a finish barrier. Its non-FALSE
actions retain their original zero-based indices and declaration order. An action
may have refresh nodes, which run conceptually after that action and before the
next action. This creates establish → refresh → configure paths without introducing
provider-specific graph logic. Empty modules still have a completion barrier.

Modules without dependency edges remain independent. Stable topological ordering
uses profile/module and action declaration order to break ties. This ordering is
not a parallel scheduler and is not permission to execute DEFERRED nodes. Provider
resource constraints remain attached to plans for the later scheduler.

FALSE modules/actions are omitted. DEFERRED gates/actions remain in the graph so
their work is not lost. Dependency metadata conditioned on them is withheld until
their condition is TRUE. An inactive/deferred module must propagate that gate to
all of its action selection results.

## Dependencies

Module `requires`/`after` edges connect a target module's finish to the consuming
module's start. Action configuration and provider plans can add the same module
dependencies at the action node. Hard requirements must be selected and not FALSE;
there is no automatic module discovery or inclusion. A DEFERRED target remains a
blocking dependency, never a satisfied one. Missing/unselected/FALSE hard targets
raise a contextual error; soft `after` targets in those states generate warnings
and no edge. Active self-dependencies are cycles.

All snapshots are topologically validated before return. Errors show an actual
cycle path, including module gates, actions and refresh nodes where applicable.
The cycle finder is iterative so long action chains do not exhaust recursion.

## Fact relationships

Refresh references come from action metadata and provider plans; inputs come from
provider plans and waiting condition results. All referenced facts must be declared
in a selected module or be one of the global built-ins. Global and scoped fact
identities stay distinct.

`FactLink(producer, consumer, fact)` establishes an explicit refresh edge when the
producer is not already ordered before its consumer. The producer must be an action
with a matching refresh declaration; the consumer must declare that fact as an input
or a waiting condition. A consumer can be an action or a deferred module start gate.
Links participate in ordinary cycle detection. The graph does not guess a producer
from matching program names or silently choose between unrelated installers.

`graph.earlier_refresh(consumer)` returns evidence usable by the condition evaluator.
Only ancestor refresh nodes qualify, and their producer must have a TRUE outcome
and a non-SKIP provider plan. Every preceding gate/action on that producer's path
must also be TRUE. An unrelated, self-dependent, skipped or deferred producer cannot
justify deferral. If multiple qualifying refreshes exist, the last in stable order
provides the diagnostic identifier; all graph edges remain intact.

## Integration boundary

The planner coordinates initial condition results, provider plans and graph
rebuilding. Explicit fact links remain available through the graph API. This API does not discover links, gather facts, execute
actions, mark actions successful, validate ownership or schedule resource locks.
The [staged executor](applying.md) invalidates declared facts after successful
producer execution, reevaluates conditions and revalidates pending dependencies
and ownership before applying configuration. Graph evidence describes potential eligible predecessors, not a
guarantee that an external installer will succeed.

Source is separated into node records, graph storage/evidence, dependency resolution,
snapshot construction and topology algorithms under `etchlib/graph/`.
