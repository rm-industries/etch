# Etch

<img src="website/public/logo.svg" alt="Etch logo" width="96" height="96">

**Make your environment yours.**

A portable, declarative environment manager for applying, composing, and sharing
the configuration that makes a machine yours.

## Development status

Etch is being built. The checkout-local CLI supports fact and repository diagnostics and
non-mutating, provider-aware plans, including conditions, facts, dependency order
and destination ownership checks. Staged `apply` refreshes declared facts and
revalidates newly active work. Use `--jobs` for [resource-aware concurrency](docs/scheduling.md).
Further integrations are tracked in the [roadmap](https://github.com/rm-industries/etch/issues/2).

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
command reports current-state errors and explains inspection limits.

Use [`plan`](docs/planning.md) for provider validation and inspection. It reports
known changes, skips and deferred conditions without applying actions or downloading
installers. Requested version facts may run inspection commands.
Use [`apply`](docs/applying.md) with the same module/profile selection when ready
to make changes. It stops on the first failure and reports remaining work as blocked.

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
changes through the provider API and staged CLI application.
The [clean provider](docs/clean.md) uses local link receipts to remove proven broken
or explicitly retired links while preserving unowned content.
Core [shell and script providers](docs/commands.md) support imperative commands,
module-owned scripts, checks, environment metadata and explicit privilege requests.
The [installer provider](docs/installers.md) downloads and validates upstream scripts
before executing a temporary local copy, with per-download TLS and checksum controls.

The external [VS Code reference plugin](plugins/vscode/README.md) reconciles missing
extensions and provides command, version and extension facts. It is loaded only
when declared in the consumer configuration.

The external [Homebrew reference plugin](plugins/homebrew/README.md) installs missing
formulae and casks, supports explicit command/version fact refresh, and serializes
package-manager changes through the generic resource scheduler.

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
shows CLI help; use an explicit command to inspect or apply configuration.

The minimal example does not itself vendor Etch. To try the launcher, first place
Etch source in that example's `vendor/etch` directory. The bootstrap tests construct
both vendored and recursive-clone consumer fixtures in temporary directories.

See [initial architecture decisions](docs/decisions/0001-foundation.md) for the
configuration layout, proposed provider contracts and disposition of open questions.
The checked-in example is generic; personal environment configuration belongs in
consumer repositories.

### Diagnostics

Use `./etch facts --profile developer` to inspect scoped fact values and reasons,
or `./etch doctor --profile developer` to check provider schemas, probes, the
current dependency graph, and destination claims. See [facts and doctor](docs/diagnostics.md)
for selection, exit statuses, and inspection limits.

The [generic developer profile](examples/developer/) demonstrates all eight target
modules in an isolated consumer. See its [verification evidence](docs/developer-profile.md)
for automated scenarios and the outstanding real-world migration.

Use [`etch import`](docs/importing.md) to copy a public Git module into the fixed
`modules/<name>/` consumer layout without executing it. Imports retain resolved-commit
provenance and refuse existing destinations.

Provider authors can follow the [authoring guide](docs/provider-authoring.md) for
shipped examples, execution metadata, plugin distribution and core promotion.

The [Etch website](website/README.md) is a separate Forge-generated Node project
under `website/`, targeting `https://www.rm-industries.com/etch/`. Its dependencies
and build are independent of the Python runtime.
