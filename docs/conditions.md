---
title: "Conditions"
description: "Select modules and actions with platform, presence, boolean and version conditions."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

Use `when` on a module or action to select behavior from observed state.
Conditions evaluate as true, false or deferred. False skips work; deferred waits
for an eligible earlier producer to establish a required fact.

## Predicates

```python
{'os': ['linux', 'macos']}
{'os': 'linux', 'distro': 'ubuntu', 'arch': 'x86_64'}
{'command': 'git'}
{'env': 'CI'}
{'env': {'name': 'CI', 'equals': 'true'}}
{'fact': {'name': 'tmux_version', 'matches': '>=2.1,<4'}}
{'fact': {'name': 'enabled', 'equals': True}}
{'not': {'command': 'starship'}}
```

Dictionary keys are AND. List values are OR alternatives for that key. `not`
takes one condition dictionary. Empty conditions/alternatives, unknown keys and
invalid values fail validation; version constraints are validated even if a
branch is inactive.

Platform predicates compare exact normalized strings. `command` tests executable
presence without running it. An environment name tests whether it is set, even
to an empty string; `{name, equals}` compares the string value. Absent commands,
unset variables and unavailable platform properties are false.

Fact names refer to declarations in the same module. `{name}` requires a boolean;
`{name, equals}` compares type as well as value, so `True` does not equal `1`.
`{name, matches}` uses [version comparisons](versions.md). Comparators cannot be
combined. Undeclared names, probe failures and inappropriate types are errors.

## Module and action conditions

A false module condition skips its actions. A deferred module condition defers
all its actions. With a true module condition, action conditions evaluate
individually; absent `when` means enabled. These gates do not waive declaration,
path, dependency or privilege validation when work becomes active.

## Missing facts, dependencies and refresh

A missing command-presence predicate is false. An unavailable *required named
fact*, such as a tool version, is different: it must not silently choose a version
branch. Etch defers it only when an enabled earlier action proposes actual work
and explicitly refreshes that fact along a valid dependency path. A skipped,
later, self or unrelated producer cannot justify waiting. Otherwise the required
unavailable fact is an error.

Declare the fact, order its producer before its consumer, and add `refresh` to
the producer. A module dependency supplies ordering; it does not refresh facts
by itself. After successful execution, pending conditions observe the refreshed
value. If the required fact remains unavailable, apply stops rather than waiting
forever. See [facts](facts.md) and [applying](applying.md).

`not` of a deferred condition stays deferred. False dominates AND and true
dominates OR; an unavailable observation irrelevant to the final boolean result
does not force deferral. Evaluation short-circuits in declaration order. Probe
errors actually encountered remain errors, rather than being treated as absence.
