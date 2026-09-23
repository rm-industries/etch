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
