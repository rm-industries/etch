# Loading source plugins

Declare roots explicitly in the consumer's `defaults.conf`:

```python
{
    "schema_version": 1,
    "plugins": ["vendor/etch-example"],
}
```

A root is a directory containing `etch_plugin.py`. Its entrypoint exports:

```python
from .implementation import ExampleAction

PLUGIN = {"name": "etch-example", "version": "0.1.0", "api": 1}

def actions():
    return [ExampleAction()]

def facts():
    return []
```

Factories return iterables of providers. Both factories are required, even when
empty. Metadata contains exactly the three shown fields; application releases,
plugin releases and the plugin API remain independently versioned. Version strings
are informational; this loader does not perform release dependency solving.

## Imports and distribution

The loader executes only explicitly named entrypoints. Helpers use relative imports
inside a private package namespace, so multiple plugins can have an
`implementation.py` without collisions. It does not add plugin roots to `sys.path`,
scan arbitrary Python files, discover installed packages or install dependencies.
Plugin code can itself import or execute other code; this is a trust boundary, not
an import sandbox.

Relative paths resolve against the consumer repository root. Absolute paths are
accepted for explicitly configured local development; relative paths preserve
portability. Resolved aliases of the same root are rejected. Vendored directories
and initialized Git submodules behave identically at runtime. Pin a plugin's Git
revision independently of Etch's revision; no Git command or network access is
needed by the loader after the sources have been retrieved.

## Validation and failure behavior

All root paths are checked before importing the first plugin. For each declared
plugin, loading then imports its entrypoint, validates metadata and API compatibility,
calls factories, and registers its providers. Duplicate plugin names, duplicate
provider names, attempted core shadowing, incomplete providers and factory/import
failures produce contextual errors. Declared order determines registration order.

`load_plugins(repo_root, paths, core_registry)` builds a separate registry and returns
it with plugin metadata. On failure, the caller's registry remains unchanged and
private imported modules from this load are removed. Previously loaded core provider
instances are shared; this is registration isolation, not isolation of arbitrary code.
Successful loads retain their private modules so subsequent relative imports work.
The normal CLI loads once per process; this is not a hot-reload/unload system.

Plugins are trusted executable Python. Their top-level code runs before compatibility
can be checked. Neither failures nor cleanup undo plugin side effects. The loader
does not call provider validation, inspection, planning, application or fact gathering.
It cannot guarantee that third-party factories refrain from performing those effects
themselves. Review plugin source before declaring it, including when running doctor.

## Diagnostics and scope

`etch doctor` loads declared plugins and reports their name, release, compatible API
and resolved root. It still checks module structure rather than provider-specific
payloads, facts, graph correctness or destination conflicts. Core providers are not
yet shipped, so doctor does not yet require every declared action name to resolve.

The implementation separates metadata validation (`metadata.py`), Python imports
(`source.py`) and loading/registration orchestration (`loader.py`). Tests include
relative-import isolation, rollback of registrations, core shadowing, incompatible
metadata, and a recursive local clone with independently pinned engine/plugin sources.
