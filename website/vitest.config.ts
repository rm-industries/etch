/// <reference types="vitest/config" />
import { getViteConfig } from 'astro/config';

export default getViteConfig({
  test: {
    include: ['src/**/*.test.ts', 'scripts/**/*.test.ts'],
    coverage: {
      include: [
        'src/config/**/*.ts',
        'src/content.config.ts',
        'src/integrations/**/*.ts',
        'src/lib/**/*.ts',
        'src/themes/site-theme.ts',
      ],
      provider: 'v8',
      reporter: ['text', 'html'],
      thresholds: {
        branches: 100,
        functions: 100,
        lines: 100,
        statements: 100,
      },
    },
  },
});
