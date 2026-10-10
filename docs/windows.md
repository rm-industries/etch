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

This is runtime qualification, not full Windows provider support. Filesystem
ownership and symlinks (#106), PowerShell/scripts (#107), installers (#108),
Registry preferences (#109), and comprehensive integration coverage (#110)
remain pending. Do not assume POSIX shell commands, sudo, executable permission
bits, Homebrew, Git import, or Unix-only reference profiles work on Windows.
Windows Server and WSL are outside the native baseline; WSL follows Linux rules.
