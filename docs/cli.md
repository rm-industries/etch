---
title: "CLI reference"
description: "All commands and options, their defaults, selection rules, output and exit behavior."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# CLI reference

Run `etch --help` for the command list and `etch <command> --help` for its options.
The core engine prints help when invoked without a command. The template's `./etch`
launcher instead defaults to `plan --profile developer`; that is a consumer choice.

## Commands

| Command | Purpose | Options |
| --- | --- | --- |
| `plan [modules...]` | Inspect proposed changes; does not apply them | `--repo`, `--profile`, `--verbose` / `-v`, `--timings` |
| `apply [modules...]` | Build a fresh plan and execute eligible actions | `--repo`, `--profile`, `--jobs` / `-j`, `--allow-sudo`, `--verbose` / `-v`, `--timings` |
| `doctor [modules...]` | Diagnose setup, declarations, facts and the current plan | `--repo`, `--profile` |
| `facts [modules...]` | Gather all declared facts in selected modules | `--repo`, `--profile` |
| `format [files...]` | Format module/profile configuration | `--repo`, `--check` |
| `validate` | Validate declarations without inspecting or applying state | `--repo` |
| `import SOURCE` | Copy a public Git module into the consumer | `--repo`, required `--path`, `--ref`, `--no-provenance` |
| `update` | Pull the consumer's upstream, then synchronize recorded submodule pins | `--repo` |
| `submodules update` | Synchronize pins already recorded locally, without pulling | `--repo` |

`etch --version` reports the engine version. Every command supports `--help` / `-h`.

## Repository and selection

`--repo PATH` selects the consumer repository root, not the engine directory.
Without it, the engine uses the current directory. A symlink-aware consumer launcher
can select its own checkout from elsewhere; it does not infer a different consumer
from whatever directory you happen to be in.

Plan, apply, doctor and facts accept **either** explicit module names **or** a
profile. Combining them is an error. With neither, all discovered modules are
selected in lexical order. A profile supplies its listed order; dependencies may
constrain execution. `requires` and `after` do not automatically select modules.
Filtering selects work and probes, but does not excuse malformed configuration
elsewhere in the consumer.

```sh
etch plan git zsh --repo ~/dotfiles
etch apply --profile developer --repo ~/dotfiles
```

## Output, performance and privilege

`plan --verbose` expands observations, dependency order, claims, resource limits,
facts and provider details. It does not run actions. `apply --verbose` streams
command output instead of hiding successful output. These flags serve different
purposes; neither grants privileges or changes module selection.

`--timings` is available on plan and apply. It appends provider call counts and
durations to stderr without enabling command output. It can be combined with
`--verbose`. It omits configuration/arguments from its own report, but ordinary
verbose output and failure diagnostics can still contain sensitive data.

`--jobs N` allows up to 1–64 independent actions concurrently and overrides
`execution.jobs` in `defaults.conf`. Dependencies, fact refreshes and shared
resources still constrain concurrency. More jobs do not authorize elevation or
permit simultaneous mutations of a locked package manager. See [scheduling](scheduling.md).

`--allow-sudo` authorizes actions that explicitly request `sudo: True`, including
ones activated after refresh. It does not elevate the whole process or add sudo
to other actions. Interactive commands remain serialized. On Windows, `sudo`
actions are unsupported; see [Windows usage](windows.md).

## Formatting, imports and updates

`format --check` reports differently formatted files without writing them and returns 1
when changes are needed. `format` writes canonical layout and preserves supported
comments. Neither validates desired filesystem state. `validate` checks declarations
and loads declared plugins as trusted code; it does not run actions. See [configuration](configuration.md).

`import --ref` chooses a full commit ID or full branch/tag ref; the default is
remote HEAD. `--no-provenance` omits the informational sidecar. Import is a copy,
not an installation or update mechanism; see [importing](importing.md).

`update` uses Git's fast-forward/autostash behavior and stops before pin setup if
restoring edits leaves unresolved conflicts. It does not run apply afterward.
`submodules update` initializes/aligns the recorded pins without pulling or advancing
them upstream. Both require the consumer Git root and an initialized engine;
see [updates and submodules](submodules.md).

## Results and errors

Normal success returns 0. Validation, planning, provider failures and
`format --check` differences return 1. Argument usage errors return 2. Git update
commands preserve Git's failure status; Etch's own setup/conflict errors return 1.
Do not treat an arbitrary nonzero status as a successfully applied configuration.

Plan statuses describe proposed work; apply statuses describe actual outcomes.
`CHANGED` and `UNCHANGED` are successful application outcomes, `SKIPPED` means
no execution was needed or allowed by the condition, and `FAILED` / `BLOCKED`
require attention. An action failure blocks its module and dependent chains through `requires`
and `after`; independent modules continue. Safety errors and interruption stop new
dispatch while in-flight work finishes. Neither failure nor interruption rolls back earlier effects.
Read [planning](planning.md), [applying](applying.md) and [diagnostics](diagnostics.md)
for the corresponding behavior and troubleshooting.
