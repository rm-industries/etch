import { flavors } from '@catppuccin/palette';
import { expect, test } from '@playwright/test';

import { site } from '../src/config/site';
import { darkTheme } from '../src/themes/site-theme';
import { resolvePreviewPath } from './preview';

test('keeps the logo legible, transparent at its corners, and inside its canvas at icon sizes', async ({
  page,
  request,
}) => {
  const logoPath = resolvePreviewPath('/logo.svg');
  const logo = await request.get(logoPath);
  expect(logo.ok()).toBe(true);
  const palette = new Set(Object.values(flavors.mocha.colors).map((color) => color.hex));
  for (const color of (await logo.text()).match(/#[\da-f]{6}/giu) ?? []) expect(palette.has(color)).toBe(true);

  await page.goto(logoPath);
  await expect(page.locator('svg')).toHaveAttribute('role', 'img');
  await expect(page.locator('svg > title')).toHaveText('Etch');
  const artworkFits = await page.locator('svg').evaluate((element) => {
    const svg = element as SVGSVGElement;
    const frame = svg.viewBox.baseVal;
    return [...svg.querySelectorAll('path')].every((path) => {
      const bounds = path.getBBox();
      const stroke = Number(path.getAttribute('stroke-width') ?? 0) / 2;
      return (
        bounds.x - stroke > frame.x &&
        bounds.y - stroke > frame.y &&
        bounds.x + bounds.width + stroke < frame.x + frame.width &&
        bounds.y + bounds.height + stroke < frame.y + frame.height
      );
    });
  });
  expect(artworkFits).toBe(true);

  await page.goto(resolvePreviewPath('/'));
  for (const size of [16, 32, 40, 96]) {
    const pixels = await page.evaluate(
      async ({ path, size }) => {
        const image = new Image(size, size);
        image.src = path;
        await image.decode();
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = size;
        const context = canvas.getContext('2d')!;
        context.drawImage(image, 0, 0, size, size);
        const data = context.getImageData(0, 0, size, size).data;
        return {
          corners: [0, size - 1, size * (size - 1), size * size - 1].map((pixel) => data[pixel * 4 + 3]),
          center: data[(Math.floor(size / 2) * size + Math.floor(size / 2)) * 4 + 3],
        };
      },
      { path: logoPath, size },
    );
    // Small icon edges are antialiased; an opaque backdrop would have alpha 255.
    expect(pixels.corners.every((alpha) => alpha < 64)).toBe(true);
    expect(pixels.center).toBe(255);
  }
});

test('keeps the informative plan and decorative header mark accessible at every layout and flavor', async ({
  page,
}) => {
  await page.goto(resolvePreviewPath('/'));
  const brand = page.getByRole('banner').getByRole('link', { name: 'Etch', exact: true });
  await expect(brand.locator('img')).toHaveAttribute('alt', '');
  expect(
    await brand.evaluate(
      (element) =>
        Number.parseFloat(getComputedStyle(element).columnGap) >=
        element.querySelector('img')!.getBoundingClientRect().width / 4,
    ),
  ).toBe(true);
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', resolvePreviewPath('/logo.svg'));

  const plan = page.getByRole('figure', { name: 'Illustrative Etch plan for a developer profile' });
  await expect(plan).toContainText('git · 1 planned change');
  await expect(plan).toContainText('zsh · 1 planned change');
  await expect(plan).toContainText('Nothing changed yet.');
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ['latte', 'frappe', 'macchiato', 'mocha']) {
      await page.locator('html').evaluate((element, value) => element.setAttribute('data-theme', value), theme);
      await expect(brand.locator('img')).toBeVisible();
      await expect(plan).toBeVisible();
      expect(await plan.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
      ).toBe(true);
    }
  }
});

test('renders a self-contained social card with current logo, loaded Fira fonts, and artwork within its canvas', async ({
  page,
  request,
}) => {
  const logo = await (await request.get(resolvePreviewPath('/logo.svg'))).body();
  const card = await (await request.get(resolvePreviewPath('/social-card.svg'))).text();
  expect(card).toContain(logo.toString('base64'));
  await page.goto(resolvePreviewPath('/social-card.svg'));
  await page.evaluate(() => document.fonts.ready);
  const fonts = await page.evaluate(() =>
    [...document.fonts].map((font) => ({ family: font.family, status: font.status })),
  );
  expect(fonts).toHaveLength(3);
  // Browsers may serialize CSS font-family strings with their surrounding quotes.
  expect(fonts.map((font) => font.status)).toEqual(['loaded', 'loaded', 'loaded']);
  expect(fonts.map((font) => font.family.replace(/^(['"])(.*)\1$/u, '$2')).sort()).toEqual([
    'Fira Code',
    'Fira Sans',
    'Fira Sans',
  ]);
  const artworkFits = await page.locator('svg').evaluate((element) =>
    [...element.querySelectorAll('text, image')].every((item) => {
      const bounds = (item as SVGGraphicsElement).getBBox();
      return bounds.x >= 24 && bounds.y >= 24 && bounds.x + bounds.width <= 1176 && bounds.y + bounds.height <= 606;
    }),
  );
  expect(artworkFits).toBe(true);
  expect(await page.locator('svg image').getAttribute('href')).toMatch(/^data:image\/svg\+xml;base64,/u);

  await page.goto(resolvePreviewPath('/'));
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    'content',
    new URL(site.socialImage.slice(1), site.url).href,
  );
  await expect(page.locator('meta[property="og:image:alt"]')).toHaveAttribute('content', /reviewable plan/u);
  await expect(page.locator('meta[name="twitter:image"]')).toHaveAttribute(
    'content',
    new URL(site.socialImage.slice(1), site.url).href,
  );
  const raster = await page.evaluate(async (path) => {
    const image = new Image();
    image.src = path;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d')!;
    context.drawImage(image, 0, 0);
    return {
      width: image.naturalWidth,
      height: image.naturalHeight,
      background: [...context.getImageData(0, 0, 1, 1).data],
    };
  }, resolvePreviewPath(site.socialImage));
  const { r, g, b } = flavors[darkTheme].colors.base.rgb;
  expect(raster).toEqual({ width: 1200, height: 630, background: [r, g, b, 255] });
});
