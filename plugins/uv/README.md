---
title: "uv tool reference plugin"
description: "Install missing user-level Python CLI tools without changing projects or existing versions."
publishedAt: 2026-10-28
tags: [Etch, Reference]
draft: false
---

# uv tool reference plugin

This optional Python 3.9+ source bundle registers the `uv` action and `uv.command`,
`uv.version`, and `uv.tools` facts. Bundle `etch-uv` 0.1.0 uses plugin API 1 and the
shared native-command helper. It adds no Python dependencies and requires an
engine revision containing that helper's `capture` function.

Install uv and a suitable Python interpreter first. The provider does not install
uv or download Python. Native commands and default inventory output were verified
with uv 0.12.17, including an offline local-wheel install in temporary tool/bin
locations. See uv's [tools guide](https://docs.astral.sh/uv/guides/tools/) and
[storage reference](https://docs.astral.sh/uv/reference/storage/).

## Register and declare tools

In the consumer's `defaults.conf`:

```python
{
  'schema_version': 1,
  'plugins': ['vendor/etch/plugins/uv'],
  'defaults': {'uv': {'timeout': 600}},
}
```

For example, `modules/python-tools/module.conf`:

```python
{
  'schema_version': 1,
  'name': 'python-tools',
  'facts': {
    'tools': {'provider': 'uv.tools'},
    'ruff_command': {'provider': 'command', 'config': 'ruff'},
  },
  'actions': [
    {
      'uv': {'tools': ['ruff']},
      'refresh': ['tools', 'ruff_command'],
    },
  ],
}
```

Review `etch plan python-tools --verbose`, then run `etch apply python-tools`.
The module/profile controls selection. A second apply is unchanged.

`tools` is a required list of distribution names; empty lists launch no native
commands. Names normalize case and runs of `.`, `_` and `-` according to Python
package-name rules. Versions, extras, markers, Git/URL/path requirements, arbitrary
flags and Python selection are unsupported in this first schema. Existing tools
from any source satisfy presence by name, regardless of their installed version.

Only `command` (default `uv`) and `timeout` (positive finite seconds per invocation,
default `600`) are optional fields and action defaults. Command lookup follows
PATH or an explicit absolute/module-relative executable path. Facts accept the
same target options but do not inherit action defaults. Native executables are
required; Windows batch wrappers are rejected.

## Native target and configuration

`uv tool dir` and `uv tool dir --bin` select the tool environments and exposed
executables. Their absolute paths appear in plans. Native `UV_TOOL_DIR` and
`UV_TOOL_BIN_DIR` environment overrides are supported; no duplicate Etch path
options or automatic PATH edits are added. Apply pins both paths in its child
environment and rejects executable, directory or inherited-environment drift.
Ensure the bin directory is on PATH before Etch starts; use a refreshed `command`
fact to check exposure. Installed inventory alone does not prove a tool can run.

uv's tool commands ignore local project configuration and respect user/system
configuration and environment settings. Etch preserves that behavior, including
index and authentication policy. `UV_PYTHON` may select an already available
interpreter. Every install passes `--no-python-downloads`; missing suitable Python
fails explicitly rather than bootstrapping it. See uv's
[configuration rules](https://docs.astral.sh/uv/concepts/configuration-files/).

## Presence, inventory and failures

uv has no JSON tool-list option in the verified release. The provider parses only
its default plain `tool vVERSION` headers and following executable rows, with
color and progress disabled. Unexpected output, duplicate names, missing
executable rows, nonzero status, and inventory diagnostics fail explicitly.
uv can silently skip damaged tool environments with an exit-zero warning; Etch
checks stderr and refuses to interpret that incomplete list as missing tools.
Repair the environment reported by native `uv tool list`, then plan again.

Validated immutable inventory and directories are cached only within one planning
snapshot, keyed by executable, timeout, working directory and the inherited
environment fingerprint. Returned fact lists are detached copies. Empty requests
skip directory and inventory commands. Apply always rechecks fresh state and
verifies every install without using planning caches as proof of success.

uv accepts one install target at a time. Etch installs sorted missing names only,
using `uv tool install --no-python-downloads -- name>=0`; the internal specifier
forces named-package interpretation instead of accidentally installing a local
path. Existing tools, versions, unlisted entries, project files and lock files
remain untouched. No upgrade, reinstall, force, removal or cleanup is requested.
A failed sequence retains earlier successful installs; reapply installs the rest.
An exit-zero install leaving the requested tool absent is a failure.

Native resolution and package builds remain uv's responsibility. Builds can execute
code under your account; changed plans advertise network and opaque side effects.
The engine conservatively reinspects opaque plans after unrelated actions.
`package-manager:uv` serializes mutations within one Etch invocation, not other
Etch processes or external uv commands. Nothing invokes `uv add`, `uv sync`,
`uv run` or project virtual-environment operations.
