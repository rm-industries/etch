# Quality checks, dependency updates, and troubleshooting

Forge provides fast focused commands and one complete release-blocking command.
Run commands from the generated project root.

## Choose the right check

```sh
npm run quality:static
npm run quality:core
npm run quality
```

- `quality:static` checks formatting, code, CSS, Markdown, spelling, unused code,
  types, and Astro diagnostics.
- `quality:core` adds coverage-enforced unit tests, a production build, and
  required-output validation.
- `quality` adds Playwright browser/accessibility tests and Lighthouse budgets.

Use the focused command while developing and run `npm run quality` before
requesting review. The complete pipeline stops at the first failure.

## Fix common failures

### Installation fails

Confirm the Node.js and npm versions satisfy `package.json`, then retry the
committed graph:

```sh
npm ci
```

Do not delete or regenerate `package-lock.json` merely to bypass an error. If a
dependency intentionally changes, use npm to update the manifest and lockfile
together and review the resulting install scripts and package contents.

### Formatting or linting fails

Apply the available safe fixes, then rerun the reported check:

```sh
npm run format:fix
npm run lint:code:fix
npm run lint:css:fix
npm run lint:markdown:fix
```

Spelling, type, accessibility, and behavioral failures require a deliberate
source or dictionary change; do not suppress them without documenting why.

### Type checking or Astro diagnostics fail

Run `npm run typecheck` and `npm run astro:check` separately for focused output.
Check content front matter, import paths, component props, and the shared content
model before changing compiler settings.

### A browser test fails

Install the browser version required by the committed Playwright package when
working on a new machine:

```sh
npx playwright install chromium
```

Rerun `npm run test:e2e`. Screenshots and traces are written to
`test-results/`; the HTML report is written to `playwright-report/`. Both are
generated and ignored. CI retains them for failed runs.

### Lighthouse fails

Run `npm run lighthouse:ci` and inspect `.lighthouseci/`. Confirm the test used
the production build, then compare the failing route and resource type with
`docs/performance-budget.md`. Optimize the change or document a deliberately
reviewed budget revision; do not raise a threshold only to pass CI.

### The build succeeds but output is incomplete

Run `npm run validate:build`. It verifies the required pages and supporting
files and scans generated text for unresolved starter values. Add an output to
the validator when introducing a route that is part of the public contract.

### GitHub Pages does not deploy

Open the `Website Continuous Integration` workflow first. Deployment depends
directly on every applicable source and artifact check. If they pass, inspect
the `github-pages` environment, Pages source, branch restrictions, URL
configuration, and deploy job. Follow the [GitHub Pages guide](../github-pages.md)
rather than bypassing a failed dependency.

## Review dependency updates

Dependabot proposes npm and GitHub Actions updates. Before merging one:

1. read the upstream release notes and security advisory;
2. confirm the supported Node.js range and licenses remain acceptable;
3. review changes to `package.json` and `package-lock.json` together;
4. keep Sveltia updates within the exact content-model compatibility range;
5. run `npm run audit`, `npm run quality`, and any affected manual check; and
6. review the project checks and all security findings before merging.

CodeQL and dependency findings report through GitHub code scanning and
Dependabot alerts rather than blocking ordinary pull requests. Actionlint and
Zizmor block workflow changes with syntax or security defects. `npm run audit`
remains an explicit release gate and must pass—or use a reviewed, justified,
time-bounded exception—before publishing a release.

Do not widen `@rm-industries/content-model` peer compatibility inside a
generated project. Forge publishes tested content-model compatibility first,
then template dependency automation can adopt it. Existing generated projects
remain owner-maintained source and do not receive template files automatically.

High-severity audit exceptions are documented narrowly in `audit-ci.jsonc` and
`docs/performance-budget.md`. Review their expiry and exposure; do not copy an
exception to silence an unrelated advisory.

## Ask for help safely

When reporting a reproducible problem, include the Node.js and npm versions,
operating system, exact command, error output, and the smallest safe reproduction.
Remove tokens, repository secrets, private URLs, and unpublished content. Follow
the upstream Forge `SECURITY.md` process for vulnerabilities rather than opening
a public issue.
