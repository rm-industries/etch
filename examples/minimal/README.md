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

## Bootstrap a generated repository

`install.sh` (macOS/Linux) and `install.ps1` (native Windows PowerShell 5.1 or
PowerShell 7) are fresh-machine bootstraps. They require Git, clone once, and
initialize pinned submodules. They do not install prerequisites, elevate, pull,
update an existing checkout, or apply a complete profile.

GitHub does **not** rewrite script contents when generating a repository from a
template. Before sharing your installer, configure the owner-editable values at
the top of **both** scripts:

- Repository: your generated repository URL. It is initially empty and must be
  configured or supplied with `--repo URL`; there is no upstream-template fallback.
- Destination: initially `~/.dotfiles`. Edit the default or set `DOTFILES_DIR`.
- Module: initially empty, so no module runs. Set `module='etch'` in `install.sh`
  and `$module = 'etch'` in `install.ps1` to install only the user-local launcher.

`--repo URL` overrides the owner's repository default. `--module NAME` runs
exactly that one module through the existing Etch CLI after a fresh clone.
`--no-module` suppresses any configured or explicit module, regardless of flag
order. Python 3.9+ (`python3` on Unix, `python` on Windows) is required only when a
fresh install will run a module; clone-only and existing-checkout runs need no Python.

After committing these files in **your generated repository**, substitute its
owner/name in both URLs below. The downloaded script and the clone URL must refer
to the same repository. These commands become available only after your commit is
published to that repository's `main` branch:

```sh
installer=$(curl -fsSL https://raw.githubusercontent.com/YOUR-OWNER/YOUR-DOTFILES/main/install.sh) && printf '%s\n' "$installer" | sh -s -- --repo https://github.com/YOUR-OWNER/YOUR-DOTFILES.git
```

```powershell
powershell.exe -NoProfile -Command "& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/YOUR-OWNER/YOUR-DOTFILES/main/install.ps1' -ErrorAction Stop))) --repo 'https://github.com/YOUR-OWNER/YOUR-DOTFILES.git'"
```

Downloading and executing an installer trusts that repository's current code and
pinned submodules. On managed machines, or when reviewing changes, prefer downloading
and reading the script first. An immutable commit URL can replace `main`:

```sh
curl -fsSL https://raw.githubusercontent.com/YOUR-OWNER/YOUR-DOTFILES/main/install.sh -o install.sh
less install.sh
DOTFILES_DIR="$HOME/my dotfiles" sh install.sh --repo https://github.com/YOUR-OWNER/YOUR-DOTFILES.git --no-module
```

```powershell
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/YOUR-OWNER/YOUR-DOTFILES/main/install.ps1' -OutFile install.ps1
Get-Content .\install.ps1
$env:DOTFILES_DIR = Join-Path $HOME 'my dotfiles'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 --repo https://github.com/YOUR-OWNER/YOUR-DOTFILES.git --no-module
```

The reviewed-file Windows command sets execution policy only for that process;
Group Policy still takes precedence. Windows modules that create symlinks still
need Developer Mode or the appropriate session privileges. The installers do not
change those settings. To select a module, replace `--no-module` with `--module etch`
(or another module name), then open a new terminal if it updates user PATH.

An existing checkout with the expected `origin` is a **strict no-op**, even with
`--module`: no pull, submodule update, or Etch command runs. GitHub HTTPS and SSH
origins are recognized as the same repository, with or without `.git`. Other
occupied destinations, including dangling links, fail without being overwritten.
Failed clone/submodule operations can leave a partial checkout. It is retained
for inspection; a rerun does not repair it. If a module fails, resolve the error
and run Etch explicitly from the retained checkout.

Both scripts use exit 2 for invalid arguments or missing repository configuration,
127 for a missing prerequisite, and 1 for an unrelated destination. Git and Etch
failure exit codes are preserved. Bootstrap behavior is tested with local generated
repositories and recursive submodules, on Unix and both Windows PowerShell hosts.
