import { defineConfig } from 'cspell';

export default defineConfig({
  // Ignore only installed dependencies and generated tool output.
  ignorePaths: ['node_modules', 'dist', 'coverage', 'playwright-report', 'test-results', '.lighthouseci'],
  words: [
    'autorun',
    'Catppuccin',
    'contentinfo',
    'daisyui',
    'Fira',
    'fontsource',
    'GHSA',
    'lhci',
    'lighthouseci',
    'Macchiato',
    'prefersdark',
    'Sveltia',
    'unreviewed',
    'WCAG',
    'Zizmor',
  ],
});
