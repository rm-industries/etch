---
title: Facts and providers
description: Observe the environment, plan explicit changes, and extend capabilities through providers.
publishedAt: 2026-09-22T10:00:00Z
tags:
  - Etch
  - Providers
draft: false
---

Facts describe observed state: a platform, a command, a version, or a provider's
inventory. Conditions use those facts to select actions. An unavailable fact is
not automatically false; a required observation needs a valid producer or a clear error.

## Establish, refresh, configure

An installer can establish a tool, explicitly refresh a declared version fact,
and unlock configuration that depends on that version. Etch reinspects newly
active actions and their destination claims before applying them.

## Providers implement capabilities

Core includes filesystem and command providers. VS Code and Homebrew are reference
plugins loaded only when their source bundles are explicitly declared. Plugins are
trusted executable code; review them before loading, including during diagnostics.

Providers declare dependencies, owned paths, fact inputs, refreshes, and shared
execution resources. Homebrew operations share `package-manager:brew`, allowing
unrelated work to proceed without overlapping package-manager mutations.

The [provider authoring guide](https://github.com/rm-industries/etch/blob/main/docs/provider-authoring.md)
connects these contracts to the shipped implementations and their tests.
