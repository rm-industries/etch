---
title: Migrating from Dotbot
description: Move links and bootstrap commands into explicit Etch modules.
publishedAt: 2026-09-23T10:00:00Z
tags:
  - Etch
  - Migration
draft: false
---

Migrate one capability at a time. Dotbot's install file and plugins can combine links, directory creation, cleanup, and
shell commands. Etch instead puts each capability in a module, selects modules through a profile, and shows a plan
before applying. Keep the old installation available while you compare the proposed destinations.

| Dotbot concept | Etch approach |
| --- | --- |
| `link` directive | `link` action with module-relative source assets |
| `create` directive | `create` action for directories |
| `shell` directive | `shell` action for short commands or `script` for a module-owned executable |
| installer shell command | `installer` for a verified HTTPS upstream script, or `script` for a checked-in installer |
| install file order | action order, `requires`, or `after` between selected modules |
| plugin command | explicit Etch provider plugin if available; otherwise a checked `script` or `shell` action |
| clean/force behavior | inspect ownership and provider options; do not assume Etch will replace existing paths |

Start with a simple link such as a tmux configuration. Put your `tmux.conf` in `modules/tmux/files/` and declare:

```python
{
    "schema_version": 1,
    "name": "tmux",
    "actions": [{"link": {"~/.tmux.conf": "files/tmux.conf"}}],
}
```

Select `tmux` in your profile and run `./etch plan --profile developer`. If your existing file conflicts, inspect it and
resolve the migration deliberately before applying. A `tmux -V` version fact can gate version-specific configuration,
but does not install tmux or enforce its version.

Starship's initialization line belongs in a shell configuration file managed by a module. If you also install Starship,
use a separate installer or a module-owned script with a presence check, and declare the configuration module's
dependency. Apply the same split to Oh My Zsh: installation has broad upstream side effects, while your `.zshrc` and
custom files have explicit managed destinations. Review upstream installer flags and avoid allowing both tools to
rewrite the same shell file.

For rustup and nvm, keep each upstream installation in its own module and use a check so repeat applies do not reinstall
it. Their installers may edit shell startup files, download more content, or create directories beyond Etch's ownership
claims. Prefer installer options that disable profile edits where supported, then manage initialization through a
separate link action. Pin a release URL and SHA-256 digest when upstream provides them. Do not copy illustrative
installer flags without checking the upstream release's interface.

Etch imports can help share an existing module, but `import` copies only that module. It does not translate Dotbot YAML,
install missing dependencies, copy profiles, or update an existing destination. Migrate and inspect modules one by one,
then run `doctor`, `plan`, and `apply` against a selected profile. Consult the [user guide](/etch/docs/user-guide/) for
the CLI workflow and the [installer reference](https://github.com/rm-industries/etch/blob/main/docs/installers.md) for
network and integrity rules.
