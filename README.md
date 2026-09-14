# Etch

**Make your environment yours.**

A portable, declarative environment manager for applying, composing, and sharing
the configuration that makes a machine yours.

## Development status

Etch is being built. This foundation provides a checkout-local CLI and structural
configuration checks. It does **not** apply changes yet. Provider validation,
plugins, facts, dependency planning and execution are upcoming work in the
[roadmap](https://github.com/rm-industries/etch/issues/2).

## Run from source

Python 3.9 or newer is the only runtime dependency. No installation is necessary.

```sh
./etch --version
./etch doctor --repo examples/minimal --profile developer
python3 -S -m unittest discover -v
```

`doctor` defaults to the current directory as the consuming repository root. Use
`--repo` when invoking Etch from somewhere else. Select a profile or supply module
names; with neither, it checks all discovered modules in lexical order. The
command explicitly reports which checks are not implemented yet.

Configuration uses Python literal dictionaries with `schema_version: 1`, read
through `ast.literal_eval()`. Configuration is data; plugins and scripts are code.
Literal evaluation prevents arbitrary code execution, but is not a sandbox for
hostile resource-exhaustion input.

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
