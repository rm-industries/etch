---
title: Getting started with Etch
description: Create a consumer repository, review your first plan, and apply one Git module.
publishedAt: 2026-09-22T12:00:00Z
tags:
  - Etch
  - Getting started
draft: false
---

Create your own repository from the
[Etch template](https://github.com/rm-industries/etch-template), then clone that
repository with `git clone --recurse-submodules`. The template pins the engine
and includes one generic Git configuration module. It contains no personal identity.

## Review before applying

From your consumer repository, run:

```sh
./etch
./etch doctor --profile developer
```

Bare `./etch` displays the developer plan. It does not apply changes. Review
`modules/git/files/gitconfig` and any existing home configuration before proceeding.
A conflicting existing file is refused rather than silently replaced.

```sh
./etch apply --profile developer
```

A second apply skips declarative state that is already satisfied. Opaque commands
can still report execution; inspect their behavior separately.

## Keep ownership explicit

Edit modules, profiles, and defaults in your consumer repository. Update its
engine pin deliberately. After initialization, Etch requires Python 3.9 or newer;
there is no runtime pip installation. Individual providers may require external tools.

The [template README](https://github.com/rm-industries/etch-template#readme)
explains submodule initialization, CI checks, and updating the engine.
