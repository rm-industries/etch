# Editing user documentation

User guides live in `../docs/guides/`; detailed user references also live in root
`../docs/` and the bundled-provider README files. The public collection is the
explicit list in `src/config/documentation.ts`, not every Markdown file in the repo.

## Add a document

Create a focused Markdown guide, for example `../docs/guides/configure-a-tool.md`:

```md
---
title: Configure a tool
description: Declare a module, review its plan, and apply its configuration.
publishedAt: 2026-10-14
tags: [Etch, Configuration]
draft: false
---

Explain the current behavior, then show the smallest working example.
```

Add its stable ID, repository-relative source and section to the public list.
The ID becomes `/docs/<id>/` beneath the deployment base. List order defines the
learning path and previous/next navigation. Existing guide IDs must remain stable.
The native Astro schema checks title, description, date and defaults.

Do not add a duplicate top-level heading in new guide bodies; the layout renders
`title`. Existing reference/README sources can retain their first heading for
GitHub readability; the website omits it. Use section headings for the on-page index.
Dates are feed/SEO metadata, not an invitation to present docs as a chronological blog.

Set `draft: true` for a selected document still in progress. Drafts are available
locally and excluded from production pages/feed. Do not place draft test fixtures,
experiment logs, implementation timelines or issue-completion notes in public sources.
Contributor instructions and design records remain repository-only.

## Explain behavior and interactions

Describe supported options, defaults, scope, failures and repeat behavior.
Explain interactions when they matter: selection versus dependencies, conditions
versus checks, refresh versus ordering, updates versus application, and verbosity
versus timings. Use current command names and two-space configuration examples.
Keep examples illustrative only when unavoidable, and label placeholders clearly.

Link references with source-relative Markdown paths so they also work on GitHub.
The site maps published sources to its own routes, including fragments and provider
READMEs. Contributor/example links remain GitHub links. Avoid hardcoded `/etch/`
paths in Markdown. Follow the [performance budget](../performance-budget.md) for
purposeful media and provide informative alternative text.

## Verify before publishing

```sh
npm run quality:core
npm run test:e2e
npm run preview
```

Check grouped browsing, previous/next direction, on-page headings, internal links,
mobile wrapping, terminal colors, feed/sitemap output, and absence of private records.
When adding a user capability, update its reference and relevant introductory guide
in the same PR rather than leaving a gap behind a GitHub issue link.
