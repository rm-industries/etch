---
title: Architecture reference
description: How Etch selects, validates, and schedules configuration changes.
publishedAt: 2026-09-23T11:00:00Z
tags:
  - Etch
  - Reference
draft: false
---

Etch separates configuration from execution. A consumer repository contains `defaults.conf`,
`modules/<name>/module.conf`, and `profiles/<name>.conf`. Modules own assets and actions; profiles explicitly select
modules. Core providers handle filesystem changes, commands, scripts, installers, and facts. Optional providers are
loaded only from declared plugin paths and run as trusted code.

## Observations and selection

Global platform facts and module-scoped facts describe the current environment. Conditions can test platform, command
presence, environment variables, or declared facts. An unavailable required version fact is not treated as false. It can
defer a condition only when an eligible earlier action explicitly refreshes that fact; otherwise the plan reports an
error. Once an installer runs, Etch invalidates its declared refreshed facts, observes again, and reevaluates pending
actions. Version comparison selects behavior; it does not install or upgrade a requested version. Read
[conditions](https://github.com/rm-industries/etch/blob/main/docs/conditions.md),
[facts](https://github.com/rm-industries/etch/blob/main/docs/facts.md), and
[versions](https://github.com/rm-industries/etch/blob/main/docs/versions.md) for supported syntax and limits.

## Graph, ownership, and execution

Actions retain declaration order within a module. `requires` makes another selected module a hard predecessor; `after`
adds ordering when that module is selected. The graph checks cycles and refresh relationships. Active providers inspect
state to produce plans and destination claims. Exclusive claims on the same path or ancestor and descendant paths
conflict even if one action would skip; compatible shared-directory claims can coexist. Newly activated work is
inspected and checked again before dispatch. See [graph](https://github.com/rm-industries/etch/blob/main/docs/graph.md)
and [ownership](https://github.com/rm-industries/etch/blob/main/docs/ownership.md).

`plan` is read-only with respect to managed destinations; `apply` executes staged work and refreshes relevant
observations. `--jobs` permits independent actions to run concurrently. The default is one job. Dependencies, shared
resources such as `package-manager:brew`, and interactive terminal use constrain parallelism. Providers must declare
resources and fact inputs accurately; Etch cannot infer conflicts inside opaque commands. On failure, already-running
actions finish, no new actions start, and there is no automatic rollback. See
[planning](https://github.com/rm-industries/etch/blob/main/docs/planning.md),
[applying](https://github.com/rm-industries/etch/blob/main/docs/applying.md), and
[scheduling](https://github.com/rm-industries/etch/blob/main/docs/scheduling.md).

`doctor` checks declarations, provider availability, fact probes, dependencies, ownership, and active plan errors
without applying actions. A clean diagnosis cannot guarantee a later installer succeeds or an external process leaves
the filesystem unchanged. [Diagnostics](https://github.com/rm-industries/etch/blob/main/docs/diagnostics.md) describes
what it does and does not inspect.
