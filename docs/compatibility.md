# Compatibility policy

Etch releases use SemVer tags (`vMAJOR.MINOR.PATCH`). The engine's
`etchlib.__version__` is the same version without `v`; a `-dev` checkout is not
a release. Before 1.0, a minor release may change a contract. Patch releases
fix defects without intentionally changing supported configuration or provider
interfaces. From 1.0 onward, breaking supported contracts require a major
release; additions can use a minor release.

## Independent compatibility axes

The Etch application version, configuration `schema_version`, and
`PLUGIN_API_VERSION` are separate. Application versions identify source
releases. Configuration schema 1 is currently required exactly: an unsupported
schema fails validation rather than being silently interpreted or migrated.
Plugin API 1 is also checked for exact equality before provider registration.
Changing either integer requires a documented migration path and a deliberate
compatibility decision; changing the application version alone does not change
either contract.

Each external plugin has its own `PLUGIN.version` and `PLUGIN.api` metadata.
The bundled Homebrew and VS Code examples currently declare plugin version
`0.1.0` and API 1. Their version is not derived from the Etch application
version. Consumers must pin and update an engine and each plugin deliberately;
Etch does not fetch, update, or solve plugin dependencies. A plugin's API
declaration says which engine interface it expects, not that its behavior is
safe or compatible with every external tool release.

## Supported environment and core behavior

The supported runtime matrix is Python 3.9 through 3.14 on Linux and macOS.
Core startup and execution use the Python standard library; a checkout can
run with site packages disabled. The `import` command additionally requires
Git 2.25 or newer and a public HTTPS source. Windows is not supported yet.
CI runs the full engine suite on each supported interpreter and both OSes;
the template consumer smoke also covers the minimum and newest interpreters
on both OSes.

For a released schema and application version, the core provider names and
their documented options are supported contracts: `create`, `link`, `clean`,
`shell`, `script`, and `installer`, plus the built-in fact providers. Provider
outputs describe planned behavior, but Etch cannot guarantee arbitrary shell
or installer side effects. Reference Homebrew and VS Code providers are
external plugins with their own versions and compatibility declarations, not
core providers.

Deprecations are announced in release notes with an alternative before a
supported contract is removed. Before 1.0, removal may occur in a minor
release; after 1.0, removal waits for a major release except when a security
fix cannot preserve the old behavior. Release notes must call out such an
exception. Existing schema or plugin API versions are never guessed or
automatically converted by the loader.

## Current limits

Etch has no Windows support, package dependency solver, automatic engine or
module updates, general lifecycle hooks, or automatic Dotbot translation.
`import` copies one public Git module and does not apply it or import its
dependencies. Core `providers` and `plugins` listing commands are deferred;
`doctor` reports loaded providers and plugin compatibility. External tools,
network endpoints, and user-owned configuration remain the consumer's
responsibility.

See the [release procedure](releasing.md) for qualification and artifacts.
