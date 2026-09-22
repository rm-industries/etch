# Content and CMS editing

Forge stores article content as Markdown in `src/content/articles/`. Astro and
Sveltia use the same model from
`src/config/content-models/articles.ts`, so field rules are not duplicated.

## Publish an article in Markdown

Create `src/content/articles/my-first-article.md`:

```md
---
title: My first article
description: What I learned while building this site.
publishedAt: 2026-09-02
tags:
  - notes
draft: false
---

Write the article body here.
```

The file name becomes the article slug. Use a unique lowercase, hyphenated file
name. Required fields, dates, defaults, and body content are validated during
development, type checking, and builds. Do not repeat the title as a top-level
Markdown heading: the front matter `title` is the article's document title, and
the article layout renders it as the page heading.

Set `draft: true` while writing. Draft articles appear during local development
but are omitted from production article pages and RSS output. Before publishing:

```sh
npm run typecheck
npm test
npm run build
npm run validate:build
```

Then inspect the article route and `/rss.xml` in the production preview:

```sh
npm run preview
```

## Edit content with Sveltia locally

Local editing writes directly to the checked-out project; it does not require a
GitHub token.

1. Start the site with `npm run dev`.
2. Open the printed local address with `/admin/`, normally
   `http://localhost:4321/admin/`.
3. Choose **Work with Local Repository**.
4. Grant access to the generated project root, not only the content folder.
5. Create or edit an article and save it.
6. Review the resulting files with Git, run the checks above, and commit them
   through the normal project workflow.

A Chromium-based browser is the supported baseline for the local directory
picker. The browser controls directory permission; if access is denied or
revoked, reload `/admin/` and select the project again. Sveltia does not run a
separate local proxy server in this setup.

## Configure the deployed CMS

Edit `src/integrations/sveltia/config.ts` and replace:

```ts
repo: 'your-github-user/your-repository',
```

with the same `owner/repository` configured in `src/config/site.ts`. The
generated backend targets `main` and offers Sveltia's GitHub token flow. Tokens
are entered by each editor in the CMS and must never be committed to the
repository, configuration, documentation, or environment files.

Before enabling editors, decide who may push to `main`, which branch protections
apply, and whether the project needs a supported OAuth service instead of
personal tokens. Treat `/admin/` as an editing application: it is excluded from
search indexing and public Lighthouse budgets, but it is still publicly
reachable on a deployed static site.

## Change article fields

Edit only `src/config/content-models/articles.ts`. The registry passes the model
to both the Astro and Sveltia adapters.

When adding or changing a field:

1. choose whether it is required and whether it needs a default;
2. update existing Markdown files to satisfy the new model;
3. update pages or components that render the value;
4. update or add model, Astro, Sveltia, and preview tests; and
5. run `npm run quality:core` before checking the editor manually.

Do not create a separate CMS YAML schema. A second schema can drift from the
validation applied during builds.

## Media

The default CMS stores uploaded media under `public/assets/` and publishes it
from `/assets`. Add only purposeful assets, keep file sizes appropriate for the
[performance budget](../performance-budget.md), and provide useful alternative
text where media conveys meaning. Decorative imagery should use empty
alternative text at its rendering site.

## Recover from an editing problem

- If an article is missing in production, confirm `draft` is `false`, its front
  matter passes `npm run typecheck`, and the file extension is `.md` or
  `.mdx`.
- If the CMS shows the wrong fields, confirm the model is registered in
  `src/config/content-models/registry.ts` and reload the editor.
- If local CMS changes appear in an unexpected directory, revoke the browser's
  directory permission and select the project root again.
- If deployed authentication fails, verify the repository identifier, branch,
  token permissions, and organization access before changing content fields.
- If a save produced an unwanted change, use Git to inspect and restore the
  affected content file before committing it.

For broader command failures, use
[quality checks and troubleshooting](quality-and-troubleshooting.md).
