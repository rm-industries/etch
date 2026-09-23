# Developer profile verification

[The generic example](../examples/developer/) exercises git, zsh, vim, tmux,
fonts, Starship, VS Code and Homebrew together. It remains separate from personal
configuration, which belongs to its owning repository.

## Repeatable evidence

`tests/test_developer_profile.py` loads the checked-in example rather than
recreating its configuration in Python. A fresh consumer contains only the
vendored standard-library engine, explicit plugin bundles, and fixture tools.
`tests/developer_fixtures.py` reuses the existing HTTPS upstream and fake
Homebrew/VS Code CLIs. Only the Starship installer transport is replaced in the
baseline example; additional scenarios alter the relevant condition or fault.
All home changes are confined to a temporary directory.

| Scenario | Evidence |
| --- | --- |
| Fresh consumer | Vendored CLI starts under base Python `-S` with fixture-only PATH and no PYTHONPATH |
| Reviewable plan | No home mutations, package installations or installer requests before apply; plugin origins and DEFERRED state visible |
| Full apply | Generic config links, platform font directory, missing formulas/extensions, and Starship installer/configuration |
| Refresh | Starship version is initially UNAVAILABLE, installer refresh activates its link, then facts reports VALUE |
| Version branches | tmux 3.4 selects modern configuration; 2.9a selects legacy configuration |
| OS branches | Linux creates `.local/share/fonts`; macOS creates `Library/Fonts`; the opposite branch remains inactive |
| Second apply | No additional download/package/extension install; declarative actions skip, only the opaque zsh command reports CHANGED |
| Plugin API mismatch | Rejected before any home mutation or installer request |
| Cycle | Rejected before any home mutation or installer request |
| New conflict after refresh | Deferred Starship destination collides with the completed git claim; execution stops and preserves the git link |
| Package lock | Independent modules share `package-manager:brew`; a gated fake install detects concurrent entry while unrelated work releases it |

These tests run under both existing pytest and dependency-free unittest jobs on
Linux and macOS, Python 3.9 through 3.14. The OS-branch test additionally simulates
both platform identities on every runner. Fake CLI and HTTPS evidence proves
Etch's orchestration, not real package-manager/upstream behavior or font loading.
Fonts deliberately exercise only destination selection without a licensed font
payload. Existing bootstrap tests separately verify engine acquisition and
isolated imports; this suite begins with an already vendored engine.

## Template consumer smoke

The [Etch template](https://github.com/rm-industries/etch-template) is also
checked as a real consumer in `.github/workflows/template-consumer.yml`. The
workflow pins a reviewed template revision, substitutes the candidate engine
checkout for its submodule contents, and runs the template launcher on Linux
and macOS with Python 3.9 and 3.14. Both the developer profile and standalone
Git module run with an isolated home. The check verifies that bare `./etch`
only previews, `plan` and `doctor` succeed, the first apply creates the expected
Git link, and the second apply leaves declarative state unchanged. This catches
integration drift between the template and the engine without moving the
template's committed submodule pin.

The template contains generic Git configuration only. It does not replace the
eight-module fixture above or prove a personal dotfiles migration.

## Real-world dogfood evidence

The linked
[personal migration issue](https://github.com/rahul0705/dotfiles/issues/81) is open,
its acceptance checklist is unchecked, and it has no recorded run evidence in
comments. **No real developer-profile migration or installation is claimed by
this change.** No personal files, packages, or editor state were changed to
produce the automated evidence above.

Real validation remains in that owning repository, coordinated with
[Etch #23](https://github.com/rm-industries/etch/issues/23). Before calling that
portion complete, record:

- Engine/plugin revisions, OS/architecture, Python version and tool versions.
- Reviewed migration and switch-over steps, including existing file ownership.
- Fresh clone/bootstrap and plan output; successful first apply and diagnostic output.
- A second apply showing declarative no-ops and any remaining opaque commands.
- tmux branch, font destination, Starship fresh-install refresh, and plugin behavior.
- Actual limitations or failures, including whether a platform was simulated or run.

Keep secrets and personal configuration in the consumer repository; summarize
outcomes here only after real evidence exists. The automated PR references #23
without closing it, leaving the real-world evidence requirement visible.
