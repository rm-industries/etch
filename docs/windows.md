# Windows runtime baseline

The initial baseline targets Windows 11 x64 with CPython 3.9–3.14. Start Etch
from a checkout with `python -S etch`; no third-party runtime packages, POSIX
shell, elevation, or Developer Mode are needed for validation, facts, planning,
and diagnostics of a profile without platform-specific actions.

The built-in `os` fact is `windows`, `arch` normalizes `AMD64` to `x86_64`
and `ARM64` to `aarch64`, and `distro` is unavailable outside Linux. Select
Windows modules or actions with `'when': {'os': 'windows'}`. ARM64 normalization
is defined but native Windows ARM64 is not yet qualified in CI.

Paths use the host Python path rules. Module-relative executable paths accept
Windows backslashes or forward slashes; executable discovery uses Python's
`shutil.which`, including Windows `PATHEXT` for bare command names. Explicit
paths must include the executable suffix (for example `bin/tool.exe`) to work
on every supported Python version. Use native executable probes;
PowerShell invocation and batch-file execution are outside this baseline.
Home expansion follows Python's Windows `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH`
behavior rather than assuming the Unix `HOME` variable. Python configuration
strings must escape backslashes or use forward slashes.

The authoritative Project gate includes a Windows checkout smoke test on
Python 3.9 and 3.14, exercising configuration, OS conditions, command discovery,
facts, planning, diagnostics and startup with site packages disabled.

This is runtime qualification, not full Windows provider support. PowerShell/scripts (#107), installers (#108),
Registry preferences (#109), and comprehensive integration coverage (#110)
remain pending. Do not assume POSIX shell commands, sudo, executable permission
bits, Homebrew, Git import, or Unix-only reference profiles work on Windows.
Windows Server and WSL are outside the native baseline; WSL follows Linux rules.

## Filesystem contract

`create` makes directories and is a no-op when the directory exists. `link`
creates actual file or directory symlinks, with the directory type declared to
Windows explicitly. It never substitutes a junction, hard link, or copied file.
Enable Windows Developer Mode or use an account with the Create symbolic links
privilege. A privilege error explains that requirement; Etch does not elevate
itself. Replacement creates the candidate link before replacing the old link,
so failed creation preserves the old destination.

Destinations expand the native user home and resolve relative to the repository;
assets resolve inside their module. Absolute drive and UNC paths use native
Python semantics. Reject drive-relative (`C:foo`) and root-relative (`\foo`)
paths, which otherwise depend on the process drive. Forward slashes or escaped
backslashes work. Windows path comparisons are case-insensitive, and conflicting
owners fail even when destination spellings differ by case. The final destination
component remains the object managed, rather than its resolved symlink target.
Case-sensitive Windows directories are outside this initial contract.

`clean` removes only receipt-backed symlinks that are broken or explicitly
obsolete, immediately beneath selected real directories. It does not remove
regular files, directories, unowned links, junctions, or other reparse points.
Junctions are not managed destinations or cleanup roots, and receipt directories
cannot be redirected by junctions. Existing parent aliases resolve to their
actual location before ownership checks. There is no recursive cleanup.

Windows CI exercises file/directory symlinks, creation, cleanup, path conflicts,
privilege diagnostics and idempotence on Python 3.9 and 3.14. Hosted Windows
runners must permit symlink creation; those integration checks deliberately fail
rather than skip when the required capability is unavailable.
