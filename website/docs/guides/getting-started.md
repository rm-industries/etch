# Getting started and site configuration

This guide takes a newly generated Forge project from installation to a branded
local site. Run every command from the project root.

## Install and start the site

Use a supported Node.js and npm version from the `engines` field in
`package.json`, then install the committed dependency graph:

```sh
npm ci
npm run dev
```

Astro prints the local address, normally `http://localhost:4321`. Stop the
server with `Control+C`.

Use `npm ci`, rather than `npm install`, when reproducing the committed project.
Use `npm install <package>` only when deliberately changing dependencies and
commit both `package.json` and `package-lock.json` afterward.

## Change the site identity

Edit `src/config/site.ts`. The exported `site` object is the single source for
page metadata, navigation, feeds, the manifest, and CMS branding.

```ts
export const site = defineSiteConfig({
  name: 'Example Studio',
  description: 'Notes about thoughtful product design.',
  author: 'Example Team',
  url: 'https://example.com',
  repository: 'example/example-site',
  language: 'en',
  socialImage: '/social-card.svg',
  navigation: [
    { label: 'Home', href: '/' },
    { label: 'Articles', href: '/articles/' },
    { label: 'About', href: '/about/' },
  ],
  socialLinks: [{ label: 'GitHub', href: 'https://github.com/example' }],
});
```

Use the complete production URL for `url`. A GitHub Pages project site includes
its repository path, for example `https://example.github.io/example-site`.
Root-hosted and custom-domain sites use only their origin. The
[GitHub Pages guide](../github-pages.md) explains each form.

Keep `repository` in `owner/repository` form. An empty value is valid while a
repository does not exist, but configure it before using the deployed CMS.

## Replace identity assets

- Replace `public/favicon.svg` with the browser icon.
- Replace `public/social-card.svg` with the default sharing image.
- Change `site.socialImage` when the sharing image has a different path.
- Edit `src/pages/about.astro` and the homepage copy in
  `src/pages/index.astro` to describe the project.

Files under `public/` are copied to the production build without processing.
Reference them with site-relative paths and use the path helpers already used
by the template when a component must support a GitHub Pages project prefix.

## Add a page

Create an Astro file under `src/pages/` and compose the shared layout:

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
---

<BaseLayout title="Contact" description="How to contact Example Studio.">
  <h1>Contact</h1>
  <p>Send us a message.</p>
</BaseLayout>
```

Add the route to `site.navigation` if it belongs in primary navigation. Do not
add another `main` element: `BaseLayout` already supplies the document shell,
skip link, landmarks, metadata, header, and footer.

## Verify the first customization

```sh
npm run quality:core
npm run dev
```

Inspect the homepage, the changed page, `/articles/`, and `/admin/` in the
browser. Run the complete `npm run quality` gate before opening a pull request.

Continue with [content and CMS editing](content-and-cms.md), then review
[themes and accessibility](themes-and-accessibility.md).
