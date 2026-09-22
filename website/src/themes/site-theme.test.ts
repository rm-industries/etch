import { flavors } from '@catppuccin/palette';
import type { FlavorName } from '@catppuccin/palette';
import { expect, test } from 'vitest';

import { darkTheme, darkThemeColor, getCatppuccinDaisyOptions, lightTheme, lightThemeColor } from './site-theme.ts';

test('derives browser colors from the configured Catppuccin flavors', () => {
  expect(lightThemeColor).toBe(flavors[lightTheme].colors.base.hex);
  expect(darkThemeColor).toBe(flavors[darkTheme].colors.base.hex);
});

test('marks exactly one light default and one preferred dark theme', () => {
  const flavorNames = Object.keys(flavors) as FlavorName[];
  const defaults = flavorNames.filter((flavor) => getCatppuccinDaisyOptions(flavor).default);
  const preferredDark = flavorNames.filter((flavor) => getCatppuccinDaisyOptions(flavor).prefersdark);

  expect(defaults).toEqual([lightTheme]);
  expect(preferredDark).toEqual([darkTheme]);
});
