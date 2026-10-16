---
title: "Upstream installers"
description: "Download and execute checked upstream installers with TLS, checksums and presence checks."
publishedAt: 2026-10-14
tags: [Etch, Reference]
draft: false
---

# Upstream installers

The core `installer` provider downloads an upstream script to a private temporary
directory, validates the complete response and optional SHA-256 digest, then runs
the local copy. It never pipes a network response into a shell. Use `etch plan` to review an
installer and `etch apply` to run it.

```python
{
  "installer": {
    "url": "https://upstream.example.invalid/releases/v1/install.sh",
    "shell": "/bin/sh",
    "args": ["--yes", "--no-modify-path"],
    "env": {"PROFILE": "/dev/null"},
    "check": {"command": "example-tool"},
    "download_timeout": 30,
    "timeout": 300,
  },
  "refresh": ["version"],
}
```

This illustrative URL and flags must be replaced with the upstream project's
actual supported interface. Use that interface to disable shell-profile edits;
manage shell initialization and configuration with separate Etch `link` actions.
Installers make no path ownership claims because their effects are opaque. Etch
cannot prevent an arbitrary upstream script from modifying other files.

## Checks, planning and execution

Checks use the same `command`, `path_exists`, `file_exists` and `directory_exists`
predicates as [shell/script actions](commands.md). Passing checks produce `SKIP`;
otherwise plans report `RUN`, the URL, network access and opaque executable effects.
Inspection and planning never download or execute an installer. Checks are repeated
before application, so newly installed software is not installed again from an old
plan. With no check, every application runs the installer; no automatic updating or
version reconciliation is inferred.

`shell` names one executable (default `/bin/sh`), not a command string. Execution
passes the temporary filename and each `args` item separately, without shell
interpolation. The module directory is the working directory. `env`, Etch's context
variables, `description`, `quiet`, `stdin` and `sudo` follow the shell/script contract.
Privilege requests are visible in the plan and require `etch apply --allow-sudo` before
any download. Downloads themselves use the current process's privileges. Temporary
files are removed on download, checksum and execution failures as well as success;
upstream side effects are not rolled back.

Installer defaults may set common execution options, `shell`, `tls` and
`download_timeout` and `expand_home`. URL, arguments and checksum must be explicit on the action.
Nested dictionaries are replaced, not merged, when an action overrides defaults.

## TLS and integrity

Only HTTPS URLs are accepted; embedded credentials, fragments and whitespace are
rejected. Certificate and hostname verification are enabled by default. A module
may add its own CA trust with `"tls": {"ca_file": "files/company-ca.pem"}`. The file
must stay within the module root. An explicit `"tls": {"verify": False}` disables
verification for that download and is shown in its plan. Combining a CA file with
disabled verification is rejected. No process-global TLS settings or urllib opener
are changed.

Optional `sha256` must contain exactly 64 hexadecimal characters and is compared
against the downloaded bytes before execution. An immutable URL plus a checksum
pins installer content; a live URL without a hash intentionally follows upstream.
Checksums do not make upstream script behavior declarative.

## Transfer and failure policy

- One request attempt; no automatic retries after network or execution failure.
- Redirects are rejected, including HTTPS redirects. Configure the final HTTPS URL.
- Require HTTP 200, a nonempty body and at most 8 MiB. When supplied, Content-Length
  must be valid and match the received body. Partial responses, encoded responses
  and HTML error pages are rejected. Other content types are allowed because script
  hosting services vary; the checksum is the optional content-integrity guarantee.
- `download_timeout` defaults to 30 seconds per blocking network operation. It is a
  socket timeout, not a total wall-clock deadline for a slowly streaming response.
- `timeout` defaults to 300 seconds for the interpreter process. Both timeout values
  must be positive finite seconds. Execution failure stops the action; there is no
  retry and no automatic rollback of changes made by the script.

## Current-user home paths

Arguments and environment values are literal by default. Set `expand_home` to
`True` to expand a leading `~` in installer `args` and configured `env` values:

```python
{
  'installer': {
    'url': 'https://upstream.example.invalid/install.sh',
    'expand_home': True,
    'args': ['-b', '~/.local/bin'],
    'env': {'BIN_DIR': '~/.local/bin'},
    'check': {'file_exists': '~/.local/bin/example-tool'},
  },
}
```

Replace this illustrative URL, flags and check with the upstream interface.
Only `~` or a leading `~/` expands; Windows also accepts a leading `~\`.
The home comes from Python's native current-user home lookup, including Windows
`USERPROFILE`/`HOMEDRIVE`/`HOMEPATH`. Expansion happens during normalization,
before execution and elevation, using the account running Etch. Spaces and
shell punctuation in the home remain part of one argument. `$HOME`, `${HOME}`,
`%USERPROFILE%`, `~another-user`, embedded tildes and shell expressions stay literal.
No general variable interpolation or shell evaluation is added. The option does
not expand URLs, interpreter names or inherited environment variables, and it
does not create directories. Existing check predicates keep their own path
expansion behavior. Consumers may set the boolean in installer defaults and
override it per action with `False`.

## Validate shared platform configuration

`etch validate` checks every installer declaration structurally, including actions
excluded by module or action conditions. It accepts Unix and PowerShell interpreter
names on any host, so a shared repository can validate on Windows, macOS and Linux.
Malformed options and conditions still fail, even in inactive declarations.

Use OS guards to select the appropriate installers. Active installers are checked
against the current host during inspection and again before application. On Windows,
only `pwsh` and `powershell.exe` installers are supported; a Unix interpreter is
rejected before presence checks, downloads or execution. Static validation does not
prove that an interpreter is installed or supported on the current host.
