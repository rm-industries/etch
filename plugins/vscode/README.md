# VS Code reference plugin

This bundle supplies the `vscode` action and `vscode.command`, `vscode.version`,
and `vscode.extensions` fact providers. It stays external to Etch core and must be
explicitly loaded. It requires Python 3.9+ and the standard library only.

Copy this directory into a consumer as `vendor/etch-vscode`, or reference it inside
a vendored Etch checkout. Declare it in the consumer's `defaults.conf`:

```python
{
    "schema_version": 1,
    "plugins": ["vendor/etch-vscode"],
    "defaults": {
        "vscode": {"command": "code", "timeout": 120},
    },
}
```

The monorepo path is `plugins/vscode`, following the reference-bundle placement
[decision](../../docs/decisions/0001-foundation.md). The entrypoint metadata identifies
`etch-vscode` version `0.1.0`, plugin API 1. `etch plan --verbose` shows that origin;
core registration does not load or register this bundle.

## Configure extensions and observations

Example `modules/editor/module.conf`:

```python
{
    "schema_version": 1,
    "name": "editor",
    "facts": {
        "editor_command": {"vscode.command": {}},
        "editor_version": {"vscode.version": {}},
        "editor_extensions": {"vscode.extensions": {}},
    },
    "actions": [
        {
            "vscode": {
                "extensions": [
                    "astro-build.astro-vscode",
                    "editorconfig.editorconfig",
                    "ms-python.python",
                ],
            },
            "refresh": ["editor_extensions"],
        },
    ],
}
```

Run `etch plan editor` to inspect, then `etch apply editor` to reconcile. Install VS
Code and make its `code` command available first. On macOS, VS Code documents the
Command Palette action for installing that command in PATH. See the official
[VS Code command-line reference](https://code.visualstudio.com/docs/configure/command-line)
for command availability and extension management flags.

Action options:

| Option | Behavior |
| --- | --- |
| `extensions` | Required list of Marketplace IDs. An empty list requests no installations. |
| `command` | One executable, default `code`; absolute or module-relative paths and PATH names are accepted. No shell command strings or extra arguments. |
| `profile` | Optional VS Code profile name; passed as one argument to listing/install calls. Omission uses the CLI default profile. |
| `timeout` | Positive finite seconds per CLI invocation, default 120. |

Only `command`, `profile` and `timeout` accept action defaults. An action's value
replaces that default. Fact configurations accept the same three target options,
with their own built-in defaults; they do not inherit action defaults. Keep action
and fact targets aligned when using an alternate command or VS Code profile.

## Reconciliation and scope

IDs are trimmed, lowercased, deduplicated and sorted. This initial schema accepts
`publisher.extension` components containing letters, digits and hyphens, starting
with a letter or digit. VSIX paths, identifiers ending in `.vsix`, version pins,
removal, upgrades, pre-release and force-install options are outside initial scope.
Unknown options fail validation. Unlisted extensions are always preserved.

Inspection locates the CLI and reads `--list-extensions`. A satisfied action plans
`SKIP`; otherwise it lists missing IDs and advertises network use. Application
rechecks installed extensions, installs missing IDs in sorted order through
`--install-extension`, and verifies inventory after each installation. This also
avoids reinstalling requested members already brought in by an extension pack.
It does not parse localized installation-success messages or silently accept an
exit-zero response that leaves an extension absent.

A CLI error or timeout stops the action without retry. Extensions successfully
installed before a later failure remain installed; no rollback or removal occurs.
Reapplying observes that state and installs only what is still missing.

All actions reserve `application:vscode`, including alternate commands/profiles.
This conservative application-wide resource serializes VS Code changes across
modules. The implementation keeps no mutable provider state and does not change
the process cwd or environment.

## Facts and refresh

- `vscode.command` returns the resolved executable path without launching it.
- `vscode.version` invokes `--version` and uses Etch's supported numeric version
  parser on the first nonempty output line. Unsupported suffix formats are errors.
- `vscode.extensions` returns a sorted, unique list of lowercase installed IDs.

If the executable is missing or not executable, facts are `UNAVAILABLE`; the action
fails with guidance to install/expose the CLI. Invalid output and command failures
become fact errors through the shared provider lifecycle. Facts are lazy and cached.

Use action-level `refresh` to name each declared extension fact that must be observed
again after changes. Etch validates these references, invalidates observations after
successful execution, and gathers them when consumed. The bundle does not guess local
fact names or refresh unrelated profiles. Command/version facts normally need refresh
after installing VS Code itself, not after adding an extension. Failed actions do not
trigger refresh; a subsequent invocation gathers fresh state.

Planning runs inspection probes only and never installs extensions. Subprocesses use
argv, closed stdin, module cwd, a timeout, and bounded output reads (1 MiB per stream).
Unexpected inventory lines are rejected instead of being treated as extension IDs.

## Development

Tests load a copied bundle through Etch's real source loader and use an executable
fake CLI. No test requires an installed VS Code, network access, or real extensions.
Ruff and strict mypy include this bundle, and CI runs its tests on the same Python
3.9–3.14 Linux/macOS matrix as core.
