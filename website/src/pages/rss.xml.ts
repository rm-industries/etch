import rss from '@astrojs/rss';

import { site } from '../config/site';
import { getDocs } from '../lib/docs';
import { resolveSiteHref } from '../lib/paths';

export const GET = async () =>
  rss({
    title: site.name,
    description: site.description,
    site: site.url,
    items: (await getDocs()).map((article) => ({
      title: article.data.title,
      description: article.data.description,
      link: resolveSiteHref(`/docs/${article.id}/`),
      pubDate: article.data.publishedAt,
    })),
  });
