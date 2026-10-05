import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import { flavors } from '@catppuccin/palette';
import { chromium } from '@playwright/test';

import { darkTheme } from '../src/themes/site-theme.ts';

const colors = flavors[darkTheme].colors;
const output = new URL('../public/', import.meta.url);
const logo = (await readFile(new URL('logo.svg', output))).toString('base64');
const fonts = [
  ['Fira Sans', 400, '@fontsource/fira-sans/files/fira-sans-latin-400-normal.woff2'],
  ['Fira Sans', 700, '@fontsource/fira-sans/files/fira-sans-latin-700-normal.woff2'],
  ['Fira Code', 400, '@fontsource/fira-code/files/fira-code-latin-400-normal.woff2'],
] as const;
const fontFaces = await Promise.all(
  fonts.map(async ([family, weight, path]) => {
    const data = (await readFile(new URL(import.meta.resolve(path)))).toString('base64');
    return `@font-face { font-family: '${family}'; font-weight: ${weight}; src: url(data:font/woff2;base64,${data}) format('woff2'); }`;
  }),
);

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title description">
  <title id="title">Etch — Make your environment yours.</title>
  <desc id="description">Etch's stacked-layer logo beside an illustrative, reviewable plan for Git and Zsh modules. Nothing changed yet.</desc>
  <!-- Generated with npm run assets:generate. Embedded fonts and logo keep this image self-contained. -->
  <rect width="1200" height="630" fill="${colors.base.hex}" />
  <!-- cspell:disable -->
  <style>${fontFaces.join('\n')}</style>
  <image x="72" y="58" width="80" height="80" href="data:image/svg+xml;base64,${logo}" />
  <g fill="${colors.text.hex}" font-family="Fira Sans">
    <text x="174" y="103" font-size="52" font-weight="700">Etch</text>
    <text x="72" y="247" font-size="56" font-weight="700">Make your</text>
    <text x="72" y="313" font-size="56" font-weight="700">environment yours.</text>
    <text x="74" y="376" font-size="27">Modules you own.</text>
    <text x="74" y="414" font-size="27">Changes you can review.</text>
  </g>
  <g fill="${colors.subtext1.hex}" font-family="Fira Code" font-size="16">
    <text x="176" y="134">BY RM INDUSTRIES</text>
    <text x="74" y="554">rm-industries.com/etch</text>
  </g>
  <rect x="658" y="162" width="470" height="344" rx="18" fill="${colors.mantle.hex}" />
  <g fill="${colors.overlay0.hex}">
    <circle cx="687" cy="191" r="6" /><circle cx="707" cy="191" r="6" /><circle cx="727" cy="191" r="6" />
  </g>
  <g fill="${colors.text.hex}" font-family="Fira Code" font-size="19">
    <text x="686" y="243"><tspan fill="${colors.overlay1.hex}">$ </tspan><tspan fill="${colors.green.hex}">./etch</tspan><tspan fill="${colors.sky.hex}"> plan</tspan></text>
    <text x="686" y="289">Profile: <tspan fill="${colors.sky.hex}">developer</tspan></text>
    <text x="686" y="336">+ git · 1 planned change</text>
    <text x="710" y="365" font-size="17">~/.gitconfig</text>
    <text x="686" y="412">+ zsh · 1 planned change</text>
    <text x="710" y="441" font-size="17">~/.zshrc</text>
    <text x="686" y="482" fill="${colors.green.hex}" font-size="17">Nothing changed yet.</text>
  </g>
  <!-- cspell:enable -->
</svg>
`;

await writeFile(new URL('social-card.svg', output), svg);
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
  await page.setContent(`<style>body { margin: 0; }</style>${svg}`);
  await page.evaluate(() => document.fonts.ready);
  for (const [family, weight] of fonts) {
    if (
      !(await page.evaluate(([name, size]) => document.fonts.check(`${size} 19px "${name}"`), [
        family,
        weight,
      ] as const))
    ) {
      throw new Error(`Embedded font did not load: ${family} ${weight}`);
    }
  }
  await page.screenshot({ path: fileURLToPath(new URL('social-card.png', output)) });
} finally {
  await browser.close();
}
