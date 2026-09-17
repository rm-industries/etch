# Facts and doctor

Run diagnostics against a consumer repository before applying changes:

```sh
./etch facts --repo ~/dotfiles --profile developer
./etch doctor --repo ~/dotfiles --profile developer
./etch doctor --repo ~/dotfiles git shell
```

Both commands accept the same module/profile selection as `plan`. With neither,
all discovered modules are selected. A profile and explicit modules cannot be
combined. Configuration discovery still validates repository structure; filtering
limits module fact probes and action checks, not malformed configuration files.

## Facts

`facts` gathers global `os`, `distro`, and `arch`, plus **every declared fact in
selected modules**, including unused declarations and declarations in modules
whose conditions are false. Core and external plugin facts use the same path.
`global/os` and `module/global/os` are distinct scopes.

Each line includes VALUE, UNAVAILABLE, or ERROR and its value or reason. STALE is
an in-process cache state; these fresh command invocations gather observations.
Missing commands and unset variables are UNAVAILABLE, not probe failures. On
macOS, unavailable `distro` is expected. ERROR makes the command exit 1;
UNAVAILABLE alone does not. Facts does not inspect or run actions.

Values are displayed verbatim using Python representations. Declared environment
facts may contain secrets: review output before sharing it. Version probes run
their configured argv, and plugin facts run trusted plugin code.

## Doctor

Doctor loads explicitly declared plugins and reports their paths, release
versions, compatible API, and all registered action/fact provider origins.
Separate `providers` and `plugins` commands remain deferred for the initial
release; these essential details are always available here, including when the
current plan fails. Configuration or plugin-loading failures are reported before
any plan can be built, with a nonzero exit status.

Doctor checks:

- Python 3.9 or newer and the supported Linux/macOS platform family.
- Configuration schemas, module/plugin paths, API compatibility, duplicate and
  missing providers through normal configuration and plugin loading.
- All selected action schemas, including actions behind false/deferred gates.
- All selected fact declarations and probes, with module context on failures.
- Declared refresh references, current dependencies/cycles, conditions, resource
  names, active provider inspection, and destination ownership conflicts.
- Broken symlinks among active destination claims, including repair/removal
  candidates. It does not recursively scan arbitrary home directories.

Missing optional facts produce warnings with reasons and troubleshooting context.
Failed probes and invalid plans produce errors. An unavailable fact required by a
condition without an eligible earlier producer fails planning. An eligible future
refresh leaves a clearly reported DEFERRED gate; it is not a diagnostic failure.
Inactive/deferred actions have their schemas checked but their runtime state and
claims cannot be validated until they activate. Missing soft `after` dependencies
remain warnings. Ordinary pending changes are not failures.

Doctor exits 0 with no errors, including when warnings exist; otherwise it exits
1. Argument usage errors exit 2. Fix reported errors and rerun: declaration
errors are collected where possible, but plan construction stops at its first
failure, so additional plan errors may emerge afterward.

No action is applied, installer downloaded, link changed, or cache receipt
written. Core inspection and version probes and external plugin probes may run
commands; plugins are trusted code, not sandboxed. Opaque shell/script bodies,
network availability, eventual install success, and later filesystem changes
cannot be certified. Declare command/version facts for tools you need diagnosed.
Privileged plans can be inspected without granting permission to execute them.
