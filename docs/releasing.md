# Releasing Etch

Etch distributes tested source, not a wheel or automatic updater. Consumers
can pin a reviewed Git tag or commit as a submodule, or vendor the source
archive. The [template](https://github.com/rm-industries/etch-template) pins
an exact engine commit and updates that pin only through a consumer change.
The [compatibility policy](compatibility.md) defines the version axes and
supported platforms.

## Prepare a release

1. Finish the milestone's acceptance evidence, including the real developer
   profile dogfood tracked by [issue #23](https://github.com/rm-industries/etch/issues/23).
   Resolve known failures or document limitations before tagging.
2. Set `etchlib.__version__` to a stable `MAJOR.MINOR.PATCH` version. Review
   schema and plugin API compatibility independently. Update reference-plugin
   metadata only when those plugins themselves change.
3. Merge the change to `main`. Confirm the quality matrix passes on Linux and
   macOS for Python 3.9–3.14, including reference-plugin integration tests.
   Confirm the template consumer workflow passes for the developer profile
   and standalone Git module on both OSes with Python 3.9 and 3.14. Confirm
   the release-candidate job builds the source archive twice with identical
   bytes and runs `--version`, `doctor`, and `plan` from the extracted copy.
4. Create and push one immutable `vMAJOR.MINOR.PATCH` tag on that main commit.
   Never move or reuse a published tag; use a new patch version for a correction.

The tag starts `.github/workflows/project.yml`. The same project checks used
for pull requests run before publication: the full Python matrix, template
consumer smoke test, and release-candidate archive test. Website checks and
Pages deployment run separately in `.github/workflows/website.yml`. The
release job verifies that the tag matches `etchlib.__version__`, checks the
checkout's `--version` under Python 3.9 with site packages disabled, and
requires the tagged commit to be on `main`. Only after those gates pass does
it create a GitHub Release. A failed gate leaves no new release.

The release attaches a `git archive` source tarball and SHA-256 checksum.
The archive contains tracked source at the tagged commit, with a stable prefix
and gzip metadata suppressed; the workflow extracts it and checks startup,
diagnosis, and planning before publishing. GitHub also displays its automatic
tag source archives.
Neither archive includes a consumer's engine pin, profiles, plugins sourced
from another repository, or personal configuration.
The release description prepends the supported runtime, current schema and
plugin API versions, and key known limits to generated change notes; review
those statements during release preparation.

After publication, update the template's engine submodule pin in its own
reviewed PR and run its CI. Consumers choose when to adopt the new pin. Record
the exact release tag, schema version, plugin API version, reference-plugin
versions, supported runtime matrix, and known limitations in the release
notes. Do not tag while issue #23's real-world evidence is outstanding.
