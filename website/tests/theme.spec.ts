import { flavors } from '@catppuccin/palette';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { previewOrigin, resolvePreviewPath } from './preview';

const toRgb = (hex: string) => {
  const value = Number.parseInt(hex.slice(1), 16);

  return `rgb(${value >> 16}, ${(value >> 8) & 255}, ${value & 255})`;
};

const pageBackground = async (page: Page) =>
  page.locator('html').evaluate((element) => getComputedStyle(element).backgroundColor);

test('uses Latte for light mode and Mocha for dark mode', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto(resolvePreviewPath('/'));
  await expect(page.locator('html')).toHaveCSS('background-color', toRgb(flavors.latte.colors.base.hex));
  await expect(page.locator('main h1')).toHaveCSS('color', toRgb(flavors.latte.colors.text.hex));

  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveCSS('background-color', toRgb(flavors.mocha.colors.base.hex));
  await expect(page.locator('main h1')).toHaveCSS('color', toRgb(flavors.mocha.colors.text.hex));
});

test('uses the same terminal frame and shell token colors on the home page and in Docs', async ({ page }) => {
  for (const theme of ['latte', 'frappe', 'macchiato', 'mocha'] as const) {
    await page.goto(resolvePreviewPath('/'));
    await page.locator('html').evaluate((element, value) => element.setAttribute('data-theme', value), theme);
    const homeColors = await page
      .locator('.terminal')
      .first()
      .evaluate((terminal) => [
        getComputedStyle(terminal).backgroundColor,
        ...['command', 'option', 'argument'].map(
          (role) => getComputedStyle(terminal.querySelector(`.terminal-${role}`)!).color,
        ),
      ]);

    await page.goto(resolvePreviewPath('/docs/getting-started/'));
    await page.locator('html').evaluate((element, value) => element.setAttribute('data-theme', value), theme);
    const docsColors = await page
      .locator('.terminal')
      .first()
      .evaluate((terminal) => [
        getComputedStyle(terminal).backgroundColor,
        ...['command', 'option', 'argument'].map(
          (role) => getComputedStyle(terminal.querySelector(`.terminal-${role}`)!).color,
        ),
      ]);

    expect(docsColors).toEqual(homeColors);
  }
});

test('keeps documentation code within a small viewport', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto(resolvePreviewPath('/docs/user-guide/'));

  const terminals = page.locator('.terminal');
  expect(await terminals.count()).toBeGreaterThan(0);
  for (const terminal of await terminals.all()) {
    expect(await terminal.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(
    true,
  );
});

test('preserves focus and disabled pagination in every flavor', async ({ page }) => {
  await page.goto(resolvePreviewPath('/docs/user-guide/'));
  const navigation = page.getByRole('navigation', { name: 'Doc navigation' });
  const disabled = navigation.locator('[aria-disabled="true"]');
  const link = navigation.getByRole('link');

  for (const theme of ['latte', 'frappe', 'macchiato', 'mocha'] as const) {
    await page.locator('html').evaluate((element, value) => element.setAttribute('data-theme', value), theme);
    await disabled.focus();
    await expect(disabled).not.toBeFocused();
    await expect(disabled).not.toHaveAttribute('href');
    await expect(disabled).toHaveCSS('pointer-events', 'none');
    await link.focus();
    await expect(link).toBeFocused();
    await expect(link).not.toHaveCSS('outline-style', 'none');
  }
});

test('makes every Catppuccin flavor available explicitly', async ({ page }) => {
  await page.goto(resolvePreviewPath('/'));

  for (const flavor of ['latte', 'frappe', 'macchiato', 'mocha'] as const) {
    await page.locator('html').evaluate((element, theme) => element.setAttribute('data-theme', theme), flavor);
    expect(await pageBackground(page)).toBe(toRgb(flavors[flavor].colors.base.hex));
  }
});

test('serves fonts locally and presents a visible keyboard focus indicator', async ({ browserName, page }) => {
  const fontRequests: string[] = [];
  page.on('request', (request) => {
    if (request.resourceType() === 'font') fontRequests.push(request.url());
  });

  await page.goto(resolvePreviewPath('/'));
  await page.keyboard.press(browserName === 'webkit' && process.platform === 'darwin' ? 'Alt+Tab' : 'Tab');

  await expect(page.locator('a').first()).toBeFocused();
  await expect(page.locator('a').first()).not.toHaveCSS('outline-style', 'none');
  expect(fontRequests.length).toBeGreaterThan(0);
  expect(fontRequests.every((url) => new URL(url).origin === previewOrigin)).toBe(true);
});
