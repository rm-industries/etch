# Etch

**Make your environment yours.**

A portable, declarative environment manager for applying, composing, and sharing
the configuration that makes a machine yours.

## Development status

Etch is being built. The checkout-local CLI supports structural diagnostics and
non-mutating, provider-aware plans, including conditions, facts, dependency order
and destination ownership checks. The CLI does **not** apply changes yet; staged
execution is next in the [roadmap](https://github.com/rm-industries/etch/issues/2).

To work on Etch, start with the [contributor guide](CONTRIBUTING.md).

## Run from source

Python 3.9 or newer is the only runtime dependency. No installation is necessary.

```sh
./etch --version
./etch doctor --repo examples/minimal --profile developer
./etch plan --repo examples/minimal --profile developer --verbose
python3 -S -m unittest discover -v
```

`doctor` defaults to the current directory as the consuming repository root. Use
`--repo` when invoking Etch from somewhere else. Select a profile or supply module
names; with neither, it checks all discovered modules in lexical order. The
command explicitly reports which checks are not implemented yet.

Use [`plan`](docs/planning.md) for provider validation and inspection. It reports
known changes, skips and deferred conditions without applying actions or downloading
installers. Requested version facts may run inspection commands.

Configuration uses Python literal dictionaries with `schema_version: 1`, read
through `ast.literal_eval()`. Configuration is data; plugins and scripts are code.
Literal evaluation prevents arbitrary code execution, but is not a sandbox for
hostile resource-exhaustion input.

Schema 1 accepts dictionaries with string keys, lists, strings, numbers, booleans,
and `None`. Duplicate dictionary keys are errors, including inside provider payloads.
Tuples, sets, bytes, complex numbers, and ellipsis are unsupported. Unknown outer
fields are rejected so spelling errors cannot silently disable configuration.
Each action has exactly one provider key plus optional `when`, `requires`, `after`,
and `refresh` metadata. Each declared fact has one provider key. Conditions must
be nonempty dictionaries; evaluating their contents belongs to the condition engine.
Provider payloads are preserved for later provider-specific validation.

Module assets stay within their module root. The destination resolver expands `~`,
anchors relative destinations to the consumer repository, and preserves an existing
final symlink rather than following it to the file it points to. Environment-variable
interpolation is not supported. Resolving paths does not itself apply changes or
establish ownership claims.

Provider implementations can use `etchlib.config.compose_defaults` with an explicit
list of allowed default keys. Action options override defaults by replacing the whole
value, including dictionaries and lists. Inputs are copied, never mutated. For example,
an action's `env: {"NEW": "value"}` replaces a default `env: {"OLD": "value"}`;
the result does not retain `OLD`. Providers validate the composed options and normalize
non-dictionary payloads themselves. The loader preserves defaults without applying
them globally; provider implementations opt in during option normalization.

The [provider contracts](docs/providers.md) define shared action/fact interfaces,
typed plans and observations, and deterministic registration with origin metadata.
Core and external implementations use the same interfaces. Explicit plugin loading
is supported; engine integration is still under development.

The [fact system](docs/facts.md) supplies core platform, command, environment and
filesystem observations plus a lazy scoped cache shared with plugin facts.
The [version provider](docs/versions.md) gathers tool versions using argv commands
and supports numeric comparisons with documented patch-suffix ordering.
The [condition evaluator](docs/conditions.md) selects module/action behavior with
TRUE, FALSE and DEFERRED results, preserving work that waits on an earlier producer.
The [action graph](docs/graph.md) enforces dependencies, detects cycles and provides
validated predecessor evidence for deferred facts while retaining stable ordering.
The [ownership validator](docs/ownership.md) checks active destination claims and
rebuilds provider/graph validation when conditions activate new work.
Core [create and link providers](docs/filesystem.md) implement idempotent filesystem
changes through the provider API; CLI application is still upcoming.
The [clean provider](docs/clean.md) uses local link receipts to remove proven broken
or explicitly retired links while preserving unowned content.
Core [shell and script providers](docs/commands.md) support imperative commands,
module-owned scripts, checks, environment metadata and explicit privilege requests.
The [installer provider](docs/installers.md) downloads and validates upstream scripts
before executing a temporary local copy, with per-download TLS and checksum controls.

## Source plugins

Declare plugin roots in `defaults.conf` using `"plugins": ["vendor/etch-example"]`.
Each root contains `etch_plugin.py`, a `PLUGIN` dictionary with `name`, `version`,
and integer `api: 1`, plus `actions()` and `facts()` factories (return an empty list
for capabilities the plugin does not provide). Repository-local source, vendored
source, and initialized Git submodules use the same loader. Paths resolve against
the consumer root; explicit absolute paths are also accepted but are not portable.

`doctor` imports only declared plugins and reports compatible metadata. **Plugins
are trusted executable Python, including during diagnostics.** Entrypoint code runs
before metadata can be checked; the loader does not sandbox it or undo its side
effects. Factories run after compatibility checks, but action application and fact
gathering are not invoked by loading. See [plugin loading](docs/plugins.md) for details.

## Consumer bootstrap

Copy `examples/minimal/install` to the root of your configuration repository and
make it executable. Place a pinned Etch checkout at `vendor/etch`, using a Git
submodule or vendored source. The launcher finds Python, changes to the consumer
root, and forwards arguments and exit status. It also works when called by path
from another directory, including paths containing spaces.

```sh
git clone --recurse-submodules <your-configuration-repository>
cd <your-configuration-repository>
./install doctor --profile developer
```

The launcher reports missing Python or missing Etch source; it never downloads
Python or initializes submodules automatically. Python site packages are disabled
with `-S`. Git is needed to retrieve submodules, but neither Git nor network access
is required to start Etch after the sources are present. Bare `./install` currently
shows CLI help; application is not implemented yet.

The minimal example does not itself vendor Etch. To try the launcher, first place
Etch source in that example's `vendor/etch` directory. The bootstrap tests construct
both vendored and recursive-clone consumer fixtures in temporary directories.

See [initial architecture decisions](docs/decisions/0001-foundation.md) for the
configuration layout, proposed provider contracts and disposition of open questions.
The checked-in example is generic; personal environment configuration belongs in
consumer repositories.
