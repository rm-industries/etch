# Editing documentation

Etch stores documentation as Markdown in `../docs/guides/`. The native Astro
schema in `src/content.config.ts` validates front matter. Edit files in your
editor and review changes through Git.

## Publish an article in Markdown

Create `../docs/guides/my-first-article.md`:

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
name. Required fields, dates, and defaults are validated during
development, type checking, and builds. Do not repeat the title as a top-level
Markdown heading: the front matter `title` is the article's document title, and
the article layout renders it as the page heading.

Set `draft: true` while writing. Draft docs appear during local development
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

## Change documentation fields

Edit the schema in `src/content.config.ts`, update existing Markdown files and
any pages that render the changed fields, then run `npm run quality:core`.

## Media

Store purposeful assets in `public/assets/` and reference them through the
site path helpers. Follow the [performance budget](../performance-budget.md)
and provide meaningful alternative text for informative images.
