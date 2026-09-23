import type { APIRoute } from 'astro';

import { site } from '../config/site';
import { resolveSiteHref } from '../lib/paths';
import { darkThemeColor } from '../themes/site-theme';

export const GET: APIRoute = () =>
  new Response(
    JSON.stringify({
      name: site.name,
      short_name: site.name,
      description: site.description,
      start_url: resolveSiteHref('/'),
      display: 'standalone',
      background_color: darkThemeColor,
      theme_color: darkThemeColor,
      icons: [{ src: resolveSiteHref('/favicon.svg'), sizes: 'any', type: 'image/svg+xml' }],
    }),
    { headers: { 'Content-Type': 'application/manifest+json' } },
  );
