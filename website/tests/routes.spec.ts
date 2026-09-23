import { expect, test } from '@playwright/test';

import { site } from '../src/config/site';
import { resolvePreviewPath, resolvePreviewUrl } from './preview';

const routes = ['/', '/about/', '/docs/', '/docs/getting-started/', '/admin/', '/404/'];

test('serves every baseline page with configured canonical and social metadata', async ({ page }) => {
  for (const route of routes) {
    await page.goto(resolvePreviewPath(route));

    const canonicalUrl = new URL(resolvePreviewPath(route), site.url).href;

    await expect(page.locator('meta[name="generator"]')).toHaveAttribute('content', 'Forge by RM Industries');
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', canonicalUrl);
    await expect(page.locator('meta[property="og:site_name"]')).toHaveAttribute('content', site.name);
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', canonicalUrl);
    await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute('content', 'summary_large_image');
  }
});

test('serves the content manager without allowing search indexing', async ({ page }) => {
  await page.goto(resolvePreviewPath('/admin/'));

  await expect(page.locator('meta[name="robots"][content="noindex, nofollow"]')).toHaveCount(1);
  await expect(page).toHaveTitle(/Content Manager/u);
  await expect(page.locator('body')).not.toBeEmpty();
});

test('renders generic article tags on listings and detail pages', async ({ page }) => {
  await page.goto(resolvePreviewPath('/docs/'));
  await expect(
    page.locator(`a[href="${resolvePreviewPath('/docs/getting-started/')}"]`).getByLabel('Doc tags'),
  ).toContainText('Etch');

  await page.goto(resolvePreviewPath('/docs/getting-started/'));
  await expect(page.getByLabel('Doc tags')).toContainText('Getting started');
});

test('resolves every internal page link', async ({ page, request }) => {
  await page.goto(resolvePreviewPath('/'));

  const pending = [resolvePreviewPath('/')];
  const visited = new Set<string>();

  while (pending.length > 0) {
    const path = pending.shift();
    if (!path || visited.has(path)) continue;

    visited.add(path);
    await page.goto(path);

    const links = await page
      .locator('a[href]')
      .evaluateAll((elements) => elements.map((element) => (element as HTMLAnchorElement).href));

    for (const href of links) {
      const url = new URL(href);
      if (url.origin !== new URL(resolvePreviewUrl('/')).origin) continue;

      const linkedPath = url.pathname;
      const response = await request.get(linkedPath);
      expect(response.status(), `${path} links to ${linkedPath}`).toBeLessThan(400);

      if (!visited.has(linkedPath)) pending.push(linkedPath);
    }
  }
});

test('serves feed, crawler, manifest, and not-found metadata', async ({ request }) => {
  const feed = await request.get(resolvePreviewPath('/rss.xml'));
  expect(feed.ok()).toBe(true);
  expect(await feed.text()).toContain(new URL('docs/getting-started/', site.url).href);
  expect(await feed.text()).not.toContain('future-draft');

  const robots = await request.get(resolvePreviewPath('/robots.txt'));
  expect(robots.ok()).toBe(true);
  expect(await robots.text()).toContain(`Sitemap: ${new URL('sitemap-index.xml', site.url).href}`);

  const manifest = await request.get(resolvePreviewPath('/site.webmanifest'));
  expect(manifest.ok()).toBe(true);
  expect(manifest.headers()['content-type']).toMatch(/application\/manifest\+json/u);
  expect(await manifest.json()).toMatchObject({ name: site.name, start_url: resolvePreviewPath('/') });

  const missing = await request.get(resolvePreviewPath('/does-not-exist/'));
  expect(missing.status()).toBe(404);
  expect(await missing.text()).toContain('That page is not here.');
});

test('helps visitors recover from a missing page', async ({ page }) => {
  const response = await page.goto(resolvePreviewPath('/does-not-exist/'));

  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading', { level: 1, name: 'That page is not here.' })).toBeVisible();
  await page.getByRole('link', { name: 'Return home' }).click();
  await expect(page).toHaveURL(resolvePreviewUrl('/'));
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});
