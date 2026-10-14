import { expect, test } from '@playwright/test';

import { documentation } from '../src/config/documentation';
import { resolvePreviewPath } from './preview';

test('publishes the curated reference with usable mobile navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(resolvePreviewPath('/docs/'));
  for (const section of new Set(documentation.map((doc) => doc.section))) {
    await expect(page.getByRole('heading', { level: 2, name: section })).toBeVisible();
  }
  await page.goto(resolvePreviewPath('/docs/cli/'));
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
  await expect(page.locator('time')).toHaveCount(0);
  await page.getByText('Browse documentation', { exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Documentation topics' }).getByRole('link')).toHaveCount(
    documentation.length,
  );
  await expect(page.getByRole('navigation', { name: 'On this page' })).toBeVisible();
  const table = page.locator('article table').first();
  await expect(table).toHaveCSS('overflow-x', 'auto');
  expect(await table.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(fits).toBe(true);
});
