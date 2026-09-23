import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'astro/config';

import { getDeploymentConfig } from './src/config/deployment';
import { site } from './src/config/site';
import { shellCodeColors } from './src/lib/shell-code-colors';

const deployment = getDeploymentConfig(site.url);

export default defineConfig({
  base: deployment.base,
  integrations: [sitemap()],
  output: 'static',
  markdown: {
    shikiConfig: {
      themes: { light: 'catppuccin-latte', dark: 'catppuccin-mocha' },
      defaultColor: false,
      transformers: [shellCodeColors],
    },
  },
  site: deployment.site,
  trailingSlash: 'always',
  vite: {
    plugins: [tailwindcss()],
  },
});
