---
title: Developer profile example
description: Review and adapt a composed profile without copying personal configuration or engine test fixtures.
publishedAt: 2026-10-14
tags: [Etch, Example]
draft: false
---

# Developer profile example

The [generic developer example](../examples/developer/) shows how modules for Git,
Zsh, Vim, tmux, fonts, Starship, VS Code and Homebrew can compose one profile.
It is an example to review and adapt, not a complete personal workstation setup.

## Start with your own consumer

Use the [template](https://github.com/rm-industries/etch-template) for a minimal
consumer. Add only the modules you need and review their sources, destinations
and external commands. The generic example keeps personal identity and secrets
out of shared configuration.

## Review the example

From the engine checkout:

```sh
python3 -S etch validate --repo examples/developer
python3 -S etch plan --repo examples/developer --profile developer
python3 -S etch doctor --repo examples/developer --profile developer
```

These commands can run version probes and declared plugin inspection. Do not
apply the example to your actual home without adapting it; package and upstream
installer actions can modify more than linked files. Font examples demonstrate
platform destinations rather than supplying licensed font assets.

## Patterns to reuse

- Keep each capability in one module and assets inside that module.
- Use a profile to select work, not CI-specific module lists.
- Declare OS conditions for platform-specific actions.
- Use presence checks for opaque installers/scripts that should skip repeat work.
- Declare facts and refresh after producers when configuration depends on new state.
- Manage shell initialization separately from upstream installers that may edit it.
- Review defaults and explicitly load only the plugins your modules use.

For your consumer CI, use an isolated home on disposable runners to plan and
apply the selected profile. Install runner prerequisites your modules require.
CI should establish that your setup works; the engine's implementation tests
belong in the Etch project. See [the user guide](guides/user-guide.md),
[applying](applying.md), and the template README for the ordinary workflow.
