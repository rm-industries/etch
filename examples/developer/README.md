# Generic developer profile

This example is a fixture for Etch's first complete developer profile. It contains
no personal identity, credentials, machine paths, or third-party font binaries.
The integration suite copies it into a temporary consumer, vendors the engine and
both reference plugins, and provides isolated fake commands and a local HTTPS
installer. Run that verification from the Etch checkout:

```sh
.venv/bin/python -m pytest tests/test_developer_profile.py
```

No real Homebrew packages, VS Code extensions, or upstream installers are used by
these tests. Runtime invocations use a base Python interpreter with `-S`, a PATH
containing only fixture tools, a temporary home, and no PYTHONPATH. The test
runner itself uses the development environment.

| Module | Demonstrated behavior |
| --- | --- |
| git | Module-owned `.gitconfig`, without user identity |
| zsh | Module-owned `.zshrc`; an opaque shell no-op deliberately runs every time |
| vim | Module-owned `.vimrc` |
| tmux | Mutually exclusive configuration links selected by native version facts |
| fonts | Linux/macOS destination directory branches; no font payload included |
| starship | HTTPS installer, command check, explicit fact refresh, deferred configuration link |
| vscode | Explicit external plugin; missing-only extension installation |
| brew | Explicit external plugin; missing-only formula installation |

## Adapting the example

This is not a ready-to-run personal bootstrap. In particular, the Starship URL
uses the reserved `example.invalid` domain and will not install anything. The
integration fixture replaces its URL, interpreter and TLS CA with its local test
server. For a real consumer, choose and review an installer and its arguments,
ensure its resulting executable is on PATH, and consider pinning its checksum.
Do not let an installer take ownership of the shell files managed by this profile.

Copy the example to your own repository and vendor the engine and the two plugin
bundles. From the Etch checkout, with `consumer` set to an empty destination:

```sh
cp -R examples/developer/. "$consumer/"
mkdir -p "$consumer/.vendor/etch" "$consumer/vendor"
cp etch "$consumer/.vendor/etch/etch"
cp -R etchlib "$consumer/.vendor/etch/etchlib"
cp -R plugins/homebrew "$consumer/vendor/etch-homebrew"
cp -R plugins/vscode "$consumer/vendor/etch-vscode"
```

Review and customize the module files before running the consumer. The example
expects `brew`, `code`, and `tmux` to be available for inspection. Bootstrapping
those executables is not part of this fixture. Neither profile order nor a list
of packages implicitly creates a dependency or fact refresh across modules.
Choose explicit dependencies/refreshes if adapting it for other prerequisites.
Add actual font assets in the consumer if desired. Existing conflicting home
files are not silently replaced; review them before switching ownership.

After configuring the installer and prerequisites:

```sh
python3 -S "$consumer/.vendor/etch/etch" plan --repo "$consumer" --profile developer -v
python3 -S "$consumer/.vendor/etch/etch" apply --repo "$consumer" --profile developer --jobs 4
python3 -S "$consumer/.vendor/etch/etch" doctor --repo "$consumer" --profile developer
```

The first plan reports deferred Starship configuration when Starship is absent.
A successful installer refresh allows a new inspection and then the link. A
second apply skips established declarative state and the checked installer. The
opaque zsh shell action still reports execution; it is not evidence that a
filesystem change occurred. Remove that demonstration action in a real profile
unless you have an imperative task to run.

See [verification evidence](../../docs/developer-profile.md) for automated
coverage, limits, and the separately tracked real-world migration.
