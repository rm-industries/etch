import { expect, test } from '@playwright/test';

import { resolvePreviewPath, resolvePreviewUrl } from './preview';

test('uses primary navigation to move between pages and identify the current page', async ({ page }) => {
  await page.goto(resolvePreviewPath('/'));

  const navigation = page.getByRole('navigation', { name: 'Primary navigation' });
  await expect(navigation.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page');

  await navigation.getByRole('link', { name: 'Docs' }).click();
  await expect(page).toHaveURL(resolvePreviewUrl('/docs/'));
  await expect(page.getByRole('heading', { level: 1, name: 'Docs' })).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link', { name: 'Docs' }),
  ).toHaveAttribute('aria-current', 'page');
  await expect(navigation.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current', 'page');
});

const navigationRoutes = [
  { path: '/', current: 'Home' },
  { path: '/docs/', current: 'Docs' },
  { path: '/docs/getting-started/', current: 'Docs' },
  { path: '/about/', current: 'About' },
] as const;

test('marks only the matching desktop item and links back to RM Industries on every public route', async ({ page }) => {
  for (const route of [...navigationRoutes, { path: '/does-not-exist/', current: null }]) {
    await page.goto(resolvePreviewPath(route.path));

    const navigation = page.getByRole('navigation', { name: 'Primary navigation' });
    const currentLinks = navigation.locator('a[aria-current="page"]');
    await expect(currentLinks).toHaveCount(route.current ? 1 : 0);
    if (route.current) await expect(currentLinks).toHaveText(route.current);

    await expect(page.getByRole('contentinfo').getByRole('link', { name: 'Back to RM Industries' })).toHaveAttribute(
      'href',
      'https://www.rm-industries.com/',
    );
  }
});

test('marks only the matching mobile item, including nested Docs', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });

  for (const route of navigationRoutes) {
    await page.goto(resolvePreviewPath(route.path));
    await page.locator('summary').filter({ hasText: 'Menu' }).click();

    const navigation = page.getByRole('navigation', { name: 'Mobile navigation' });
    await expect(navigation).toBeVisible();
    await expect(navigation.locator('a[aria-current="page"]')).toHaveCount(1);
    await expect(navigation.locator('a[aria-current="page"]')).toHaveText(route.current);
  }
});

test('opens the mobile menu with the keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto(resolvePreviewPath('/docs/'));

  const toggle = page.locator('summary').filter({ hasText: 'Menu' });
  await toggle.focus();
  await toggle.press('Enter');

  const navigation = page.getByRole('navigation', { name: 'Mobile navigation' });
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Docs' })).toHaveAttribute('aria-current', 'page');
});

test('opens mobile navigation and follows a configured link', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto(resolvePreviewPath('/'));

  await page.locator('summary').filter({ hasText: 'Menu' }).click();
  const navigation = page.getByRole('navigation', { name: 'Mobile navigation' });
  await expect(navigation).toBeVisible();
  await navigation.getByRole('link', { name: 'About' }).click();

  await expect(page).toHaveURL(resolvePreviewUrl('/about/'));
  await expect(page.getByRole('heading', { level: 1, name: 'Configuration that belongs to you.' })).toBeVisible();
});

test('moves from the article listing into an article and through article pagination', async ({ page }) => {
  await page.goto(resolvePreviewPath('/docs/'));

  await page.getByRole('link', { name: /Getting started with Etch/u }).click();
  await expect(page).toHaveURL(resolvePreviewUrl('/docs/getting-started/'));
  await expect(page.getByRole('heading', { level: 1, name: 'Getting started with Etch' })).toBeVisible();

  const articleNavigation = page.getByRole('navigation', { name: 'Doc navigation' });
  await articleNavigation.getByRole('link', { name: /Modules and profiles/u }).click();
  await expect(page).toHaveURL(resolvePreviewUrl('/docs/modules-and-profiles/'));
  await expect(page.getByRole('heading', { level: 1, name: 'Modules and profiles' })).toBeVisible();
});
