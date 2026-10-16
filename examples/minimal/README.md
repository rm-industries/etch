# Minimal consumer

Copy this directory into your configuration repository and initialize a pinned
Etch checkout at `vendor/etch`. Python 3.9 or newer is required on PATH.

On Unix, run `./etch`; on Windows, run `.\etch.cmd` or `.\etch.ps1`.
A bare invocation previews the developer profile. Explicit arguments are forwarded
unchanged, including exit status, and launchers follow their links back to the
consumer checkout. The older `install` entrypoint remains a Unix bootstrap that
forwards arguments without choosing a default profile.

The developer profile demonstrates `git` and `etch`. The latter links the consumer
launcher into `~/.local/bin`: `etch` on Unix, `etch.cmd` and `etch.ps1` on Windows.
It also adds that directory to Windows **user** PATH without changing machine PATH.
Open a new terminal afterward. On Unix, add `~/.local/bin` to your shell PATH.

Before Windows `apply`, the launcher tests file and directory symlink creation
using the caller's Python process. A denied probe stops before actions run and
explains how to enable Developer Mode for ordinary, non-admin use. It never
elevates or changes Developer Mode. `plan`, `doctor`, and help remain usable.
Success in an elevated session only establishes that session's capability;
verify from your normal terminal after enabling Developer Mode. Target-directory
permissions can still prevent individual links even when the temporary probe passes.

The Windows `.cmd` wrapper permits its trusted launcher script in its own PowerShell
process without changing user or machine execution policy; organization Group Policy
still takes precedence. Direct `.ps1` invocation requires a session that permits scripts.
