# Upstream installers

The core `installer` provider downloads an upstream script to a private temporary
directory, validates the complete response and optional SHA-256 digest, then runs
the local copy. It never pipes a network response into a shell. As with the other
providers, CLI apply integration is still upcoming; the provider lifecycle is
available through the registry.

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
Privilege requests are visible in the plan and require an authorized context before
any download. Downloads themselves use the current process's privileges. Temporary
files are removed on download, checksum and execution failures as well as success;
upstream side effects are not rolled back.

Installer defaults may set common execution options, `shell`, `tls` and
`download_timeout`. URL, arguments and checksum must be explicit on the action.
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

Tests use a local HTTPS upstream and a public test-only certificate. They cover
verification, custom trust, verification disablement without global changes,
redirects, response validation, checksums, size limits, both timeouts, cleanup,
idempotence and separate Etch ownership of shell configuration. No public installer
is downloaded or run by the test suite.
