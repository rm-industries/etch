import { flavors } from '@catppuccin/palette';
import type { FlavorName } from '@catppuccin/palette';

export const lightTheme: FlavorName = 'latte';
export const darkTheme: FlavorName = 'mocha';

export const lightThemeColor = flavors[lightTheme].colors.base.hex;
export const darkThemeColor = flavors[darkTheme].colors.base.hex;

export const getCatppuccinDaisyOptions = (theme: FlavorName) => ({
  default: theme === lightTheme,
  prefersdark: theme === darkTheme,
});
