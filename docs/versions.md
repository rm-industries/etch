# Version facts and comparisons

Version facts observe installed software; they do not manage upgrades or solve
package dependencies. They use the core `version` provider and normal scoped cache.

```python
{
    "schema_version": 1,
    "name": "tmux",
    "facts": {
        "tmux_version": {
            "version": {"command": ["tmux", "-V"], "timeout": 10},
        },
    },
}
```

## Probe behavior

`command` is a nonempty argument list, never a shell string. The process runs in
the module root with the current environment and no stdin. Bare executable names
use PATH, including relative entries anchored to that module root. Explicit
relative executable paths also resolve there. Timeout defaults to 10 seconds and
must be a positive finite number. Unknown options are rejected.

Missing commands return UNAVAILABLE. An existing nonexecutable file, launch error,
nonzero exit, timeout, invalid UTF-8 or unparseable output returns ERROR with a reason.
Output is spooled to temporary files rather than buffered without bound in memory;
more than 64 KiB on either stream is rejected after execution. Spooling is not a disk
quota; probes should be short, trusted version queries. Temporary files are cleaned
up on success or failure. No curl, awk, bc or sort -V is used.

Version queries execute declared programs. A command can have side effects even
with `shell=False`; use software's supported version flag and review imported
declarations. This differs from the command-presence fact, which only inspects PATH.

## Extraction decision

Use stdout when it contains non-whitespace; otherwise use stderr (for tools such
as OpenSSH). Inspect the first nonempty line. A standalone supported version is
accepted, including a major-only version. Otherwise extract the first dotted
version-like token on that line, so `OpenSSH_9.8p1, OpenSSL 3.0.0` selects `9.8p1`.
Later lines and additional tokens do not influence selection. Leading `v` is removed.

Supported examples: `2.9a`, `3.5a`, `v22.4.1`, `Python 3.12.2`,
`git version 2.47.0`, and `OpenSSH_9.8p1`.
Unsupported suffixes are rejected rather than truncated to a numeric prefix. A
warning on the first line can make extraction fail; custom extraction rules remain
deferred until a concrete integration needs them. Facts retain the extracted string
for readable diagnostics; comparisons parse that string into a normalized value.

## Comparison decision

`parse_version` accepts dot-separated nonnegative integers, optional leading `v`,
and an optional single lowercase patch letter followed by a number. Numeric
components compare numerically; leading zeros and trailing zero components do not
affect equality. Thus `v02.1.0 == 2.1`, and `2.9 < 2.10`.

The unsuffixed release sorts before its patch suffixes. Letters compare
alphabetically and suffix numbers numerically, with a missing suffix number equal
to zero: `3.5 < 3.5a < 3.5b` and `9.8p2 < 9.8p10 < 9.9`.
Here `a` and `b` mean tool patch suffixes, not alpha/beta prereleases. This is a
deliberately small tool-version grammar, not SemVer or PEP 440. Multi-letter,
hyphenated prereleases and build metadata are unsupported.

`matches(version, constraint)` supports `==`, `!=`, `<`, `<=`, `>` and `>=`.
Comma-separated terms are AND; surrounding whitespace is allowed. For example,
`>=2.1,<4` selects current tmux configuration within that range. Every term is
validated before comparison, even when an earlier term evaluates false.
Bare constraints, wildcards, caret/tilde ranges and package solving are unsupported.

Parsing/comparison, constraint evaluation and subprocess probing are separate
modules. Condition-engine integration is #10; this change exposes the comparison
API and version fact provider without adding plan/apply behavior.
