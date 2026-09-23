import { describe, expect, it } from 'vitest';

import { resolveSiteHref } from './paths';

describe('resolveSiteHref', () => {
  it('keeps root-relative URLs unchanged for root deployments', () => {
    expect(resolveSiteHref('/docs/', '/')).toBe('/docs/');
  });

  it('prefixes root-relative URLs for project deployments', () => {
    expect(resolveSiteHref('/docs/', '/forge/')).toBe('/forge/docs/');
    expect(resolveSiteHref('/docs/', 'forge')).toBe('/forge/docs/');
  });

  it('does not prefix an existing deployment base', () => {
    expect(resolveSiteHref('/forge/docs/', '/forge/')).toBe('/forge/docs/');
    expect(resolveSiteHref('/forge', '/forge/')).toBe('/forge');
  });

  it.each(['https://example.com', '//cdn.example.com/file.svg', '#content', 'mailto:hello@example.com'])(
    'keeps non-local URL %s unchanged',
    (href) => {
      expect(resolveSiteHref(href, '/forge/')).toBe(href);
    },
  );
});
