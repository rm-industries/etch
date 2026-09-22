import { expect, test } from '@playwright/test';

test('serves the deployed site, its assets, and a mobile-safe layout', async ({ page, request }) => {
  expect(process.env.DEPLOYMENT_URL).toMatch(/^https:\/\//u);
  await page.setViewportSize({ width: 390, height: 844 });
  const response = await page.goto('');

  expect(response?.ok()).toBe(true);
  await expect(page.locator('meta[name="generator"]')).toHaveAttribute('content', 'Forge by RM Industries');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  const assetUrls = await page
    .locator('link[rel="stylesheet"][href], script[src]')
    .evaluateAll((elements) =>
      elements.map((element) =>
        element instanceof HTMLLinkElement ? element.href : (element as HTMLScriptElement).src,
      ),
    );
  expect(assetUrls.length).toBeGreaterThan(0);
  for (const assetUrl of assetUrls) expect((await request.get(assetUrl)).ok()).toBe(true);

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});
