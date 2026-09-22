import type { Config } from 'stylelint';

export default {
  extends: ['stylelint-config-standard'],
  rules: {
    'at-rule-no-unknown': [
      true,
      {
        // These directives are parsed by Tailwind and DaisyUI during the build.
        ignoreAtRules: ['apply', 'plugin', 'theme'],
      },
    ],
    'import-notation': [
      'string',
      {
        // Tailwind's bare package import is valid input for its Vite plugin.
        ignore: ['tailwindcss'],
      },
    ],
  },
} satisfies Config;
