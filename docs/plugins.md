---
title: "Loading source plugins"
description: "Load trusted source bundles explicitly and select their supported provider options."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

Plugins add action or fact providers. They are trusted executable Python, including
import-time code; review them before declaring them. Plan, validate, doctor and
facts can load declared plugins even though they do not apply configuration.

## Bundled providers

| Bundle | Action | Usage |
| --- | --- | --- |
| [uv tools](../plugins/uv/README.md) | `uv` | Install missing user-level Python CLI tools |
| [npm](../plugins/npm/README.md) | `npm` | Install missing global registry CLI packages |
| [WinGet](../plugins/winget/README.md) | `winget` | Install missing Windows packages by exact ID |
| [Homebrew](../plugins/homebrew/README.md) | `brew` | Ensure requested formulae/casks are installed |
| [Claude Code](../plugins/claude/README.md) | `claude` | Register native marketplaces and install missing user plugins |
| [Codex](../plugins/codex/README.md) | `codex` | Register native marketplaces and install missing user plugins |
| [VS Code](../plugins/vscode/README.md) | `vscode` | Install missing Marketplace extensions |
| [macOS preferences](../plugins/macos_defaults/README.md) | `macos_defaults` | Reconcile declared current-user preference keys |
| [Windows Registry](../plugins/windows_registry/README.md) | `windows_registry` | Reconcile typed current-user Registry values |

These bundles ship with the engine but are not automatically registered. If the
engine is at `vendor/etch`, declare the bundles you need in `defaults.conf`:

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/homebrew', 'vendor/etch/plugins/vscode'],
}
```

Each root contains `etch_plugin.py`. Relative roots use the consumer root;
absolute roots are accepted for explicit local use. Aliases of the same root,
duplicate plugin/provider names, incompatible APIs and attempts to override
core providers are errors. Declared order determines registration order.

## Installation and versions

The loader imports only declared source bundles. It does not discover installed
packages, fetch sources, install dependencies or add plugin roots to your Python
search path. Vendored directories and initialized Git submodules work the same
after acquisition. Plugin code may itself execute other code; this is not a sandbox.

Plugin release versions, plugin API and the engine release are independent. Pin
external bundles deliberately. Explicit [update commands](submodules.md) synchronize
the consumer's recorded pins; they do not choose newer plugin releases or solve
dependencies. [Compatibility](compatibility.md) describes supported version axes.

## Defaults, checks and diagnostics

Provider options and supported defaults belong to that provider's reference.
For example, a CLI target must resolve to the executable the provider expects;
Etch does not infer an installation from its provider name. Modules using a
platform-specific provider should declare an OS condition and any prerequisites.
Dependencies select ordering, not implicit module selection.

Run `etch doctor --profile developer` to see loaded bundles, provider origins,
API compatibility and probe/plan errors. Loading failures stop the command;
there is no fallback provider or silent override. Removing an old external
bundle is necessary if a provider has moved into core under the same name.

For writing a provider rather than consuming one, use the repository's
[provider authoring guide](provider-authoring.md). It covers lifecycle contracts,
claims, resources and tests separately from this user reference.
