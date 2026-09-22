const normalizeBase = (base: string): string => {
  const withLeadingSlash = base.startsWith('/') ? base : `/${base}`;

  if (withLeadingSlash === '/') return withLeadingSlash;

  return withLeadingSlash.replace(/\/+$/, '');
};

/** Prefix a root-relative URL with Astro's deployment base path. */
export const resolveSiteHref = (href: string, base = import.meta.env.BASE_URL): string => {
  if (!href.startsWith('/') || href.startsWith('//')) return href;

  const normalizedBase = normalizeBase(base);
  if (normalizedBase === '/' || href === normalizedBase || href.startsWith(`${normalizedBase}/`)) return href;

  return `${normalizedBase}${href}`;
};
