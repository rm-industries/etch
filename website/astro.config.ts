import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'astro/config';

import { getDeploymentConfig } from './src/config/deployment';
import { site } from './src/config/site';

const deployment = getDeploymentConfig(site.url);

export default defineConfig({
  base: deployment.base,
  integrations: [sitemap()],
  output: 'static',
  site: deployment.site,
  trailingSlash: 'always',
  vite: {
    plugins: [tailwindcss()],
  },
});
