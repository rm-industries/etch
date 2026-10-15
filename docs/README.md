# Etch documentation

These documents describe how to configure and use Etch. Public guides and selected
references are also published on the [website](https://www.rm-industries.com/etch/docs/).
They share the same Markdown sources; the website keeps reference links on-site.

## Start here

- [Getting started](guides/getting-started.md)
- [Modules and profiles](guides/modules-and-profiles.md)
- [User guide](guides/user-guide.md)
- [Migrating from Dotbot](guides/migrating-from-dotbot.md)

## Configuration and commands

- [CLI commands, flags and interactions](cli.md)
- [Configuration syntax, defaults and paths](configuration.md)
- [Facts](facts.md), [conditions](conditions.md), and [versions](versions.md)
- [Planning](planning.md), [applying](applying.md), and [parallel scheduling](scheduling.md)
- [Diagnostics](diagnostics.md), [destination ownership](ownership.md), and [compatibility](compatibility.md)

## Actions and plugins

- [Directories and links](filesystem.md), [managed-link cleanup](clean.md)
- [Shell and scripts](commands.md), [installers](installers.md), [downloads](downloads.md)
- [Loading plugins](plugins.md)
- [Codex plugins](../plugins/codex/README.md)
- [Homebrew](../plugins/homebrew/README.md), [VS Code](../plugins/vscode/README.md)
- [macOS preferences](../plugins/macos_defaults/README.md), [Windows Registry](../plugins/windows_registry/README.md)

## Maintaining a consumer

- [Updates and submodule pins](submodules.md)
- [Importing a module](importing.md)
- [Windows usage](windows.md)
- [Execution model](guides/architecture.md)
- [Generic developer example](developer-profile.md)

## Contributor material

These are repository references for maintaining or extending Etch, not the public
consumer documentation. Historical decisions are not current syntax references.

- [Development tooling](development.md) and [release procedure](releasing.md)
- [Provider authoring](provider-authoring.md) and [provider interfaces](providers.md)
- [Graph internals](graph.md)
- [Foundation decision](decisions/0001-foundation.md), [module import decision](decisions/0002-module-import.md)
- [Website maintenance](../website/README.md)

Public content is explicitly listed in `website/src/config/documentation.ts`.
Adding a Markdown file does not publish it automatically. User documentation
should explain current behavior, defaults, supported options, examples and
interactions. Investigation logs, temporary experiments and issue-completion
notes belong in their issue/PR or a separate review artifact, not these guides.
