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
notes. The real-world evidence required by issue #23 is complete.

## Optional GitLab sync

`.github/workflows/gitlab-sync.yml` copies `main` and tags to a configured GitLab
repository using the same workflow as the Etch template. In this GitHub
repository's Settings → Secrets and variables → Actions, configure:

- Repository variable `GITLAB_REPOSITORY_URL`: a credential-free HTTPS Git URL
  ending in `.git`, pointing to the core Etch destination.
- Repository secret `GITLAB_TOKEN`: a GitLab token with `write_repository` scope
  and permission to push to the destination's protected branches.

Create the GitLab destination first, preferably empty. Without the destination
variable, the sync job is skipped. After the workflow lands on `main`, pushes to
`main` or tags sync automatically; manual dispatch from `main` is also supported.
Feature branches, issues, pull requests and GitHub release assets are not copied.
The engine's source history and tags are copied; no submodule checkout is needed.

GitHub remains the source of truth while sync is enabled. Pushes are atomic and
never force updates or delete destination refs; divergent GitLab changes fail
rather than being overwritten. Credentials use a temporary askpass script rather
than the remote URL. A successful push can trigger any CI configured on GitLab.

## GitLab verification

The root `.gitlab-ci.yml` runs the Linux portion of Project CI: pinned Ruff
format/lint and mypy, pytest and standard-library unittest on Python 3.9–3.14,
startup and isolated-home diagnostics, the same pinned template-consumer smoke
matrix, and reproducible source-archive checks. The final gate runs only after
all verification jobs pass. Branch, merge-request and tag pipelines are enabled;
duplicate push pipelines for open merge requests are suppressed.

Use Linux Docker/Kubernetes runners with network access for tool installation
and the public pinned template checkout. Full Python images provide Bash and Git;
no runtime dependency is added to Etch. Mirror pushes can start these checks as
soon as this file reaches GitLab. GitHub retains native macOS/Windows qualification,
Pages, security automation and release publishing. GitLab adds Linux website
validation as described below, but does not publish duplicate releases.

## Website validation on GitLab

The scoped `.gitlab/ci/website.yml` include validates changes to `website/`,
imported `docs/guides/`, and GitLab website CI configuration. It mirrors formatting,
spelling, code/CSS/Markdown lint, unused-code checks, types and unit coverage.
One production build supplies artifact validation, Chromium/Firefox/WebKit
browser and accessibility tests, and Lighthouse. Python jobs start independently;
the Project gate depends only on the Python project checks.

GitLab retains JUnit unit/browser reports, Cobertura coverage, repository-relative
Code Quality findings, browser evidence and Lighthouse reports for seven days.
Node 26 container jobs install locked dependencies with `npm ci`; Linux runners
need network access and permission to install Playwright browser dependencies.
Lighthouse uses Playwright's Chromium with container-specific sandbox flags.

Branch, merge-request and tag pipelines retain the existing project policy.
Scheduled pipelines with a branch also run project validation; website include
change rules may admit website checks on tags or schedules without a push diff.
Duplicate branch push pipelines with an open merge request are suppressed.
These events validate only: GitLab never publishes Pages or source releases.
GitHub retains macOS/Windows qualification and authoritative publication.

The website dependency audit and GitHub dependency review remain advisory.
An advisory failure does not become a deployment prerequisite; formatting,
source/output validation, unit tests, browsers and Lighthouse remain blocking.
GitHub owns CodeQL, dependency review, Dependabot, actionlint and zizmor.
Those GitHub scanners do not validate native GitLab syntax or provide equivalent
GitLab source-security scanning. Before relying on the mirror, use the destination
server's CI Lint to validate expanded includes, rules and dependencies, and run
MR, default-branch, docs-only and CI-only changes on a real Linux runner.
No workflow contract test suite is introduced.

### Switching website deployment ownership

GitHub remains primary. GitLab Pages and deployed smoke jobs are included but
have `when: never` rules. To switch deliberately:

1. Configure GitLab Pages, its canonical site/base URL and environment protections.
   The nested `pages.publish` configuration requires GitLab 17.9 or newer.
2. Disable GitHub's website deploy, deployed smoke and Pages artifact upload step.
   Keep both providers' validation jobs enabled.
3. Replace both GitLab never rules with a rule requiring a default-branch push:
   `$CI_PIPELINE_SOURCE == "push" && $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH`.
4. Verify that every blocking website check gates publication, that the existing
   build artifact is published, and that smoke tests use a nonempty actual Pages
   URL with a ten-minute timeout. Merge requests and tags must not deploy Pages.

Changing a Pages job's environment name does not configure approval protection.
Review hosting settings separately. This procedure does not transfer source-release
publication, which remains on GitHub.
