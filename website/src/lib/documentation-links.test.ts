import { satteri } from '@astrojs/markdown-satteri';
import { expect, test } from 'vitest';

import { documentationHref, documentationLinks } from './documentation-links';

test('keeps published references on the deployed site and preserves fragments', () => {
  expect(documentationHref('facts.md#providers', 'docs/conditions.md', '/etch')).toBe('/etch/docs/facts/#providers');
  expect(
    documentationHref(
      'https://github.com/rm-industries/etch/blob/main/docs/commands.md',
      'docs/guides/user-guide.md',
      '/other',
    ),
  ).toBe('/other/docs/commands/');
  expect(documentationHref('../plugins/homebrew/README.md', 'docs/plugins.md', '/')).toBe('/docs/homebrew/');
});

test('keeps external links and sends unpublished source references to GitHub', () => {
  for (const href of [
    '#checks',
    '/etch/docs/',
    'mailto:team@example.com',
    'https://example.com',
    'http://example.com',
  ]) {
    expect(documentationHref(href, 'docs/plugins.md', '/etch')).toBe(href);
  }
  expect(documentationHref('provider-authoring.md', 'docs/plugins.md', '/etch')).toBe(
    'https://github.com/rm-industries/etch/blob/main/docs/provider-authoring.md',
  );
  expect(documentationHref('../examples/developer/', 'docs/developer-profile.md', '/etch')).toBe(
    'https://github.com/rm-industries/etch/tree/main/examples/developer/',
  );
});

test('rewrites Markdown links and reference definitions without duplicate page headings', async () => {
  const renderer = await satteri({
    mdastPlugins: [documentationLinks({ root: '/repo', base: '/etch' })],
  }).createRenderer({});
  const result = await renderer.render(
    '# Conditions\n\n[Fact options](facts.md) and [versions][version].\n\n[version]: versions.md\n\n## Selection',
    { fileURL: new URL('file:///repo/docs/conditions.md') },
  );
  expect(result.code).not.toContain('<h1');
  expect(result.code).toContain('href="/etch/docs/facts/"');
  expect(result.code).toContain('href="/etch/docs/versions/"');
  const nested = await renderer.render('Text first.\n\n# Keep this heading\n\n> # Nested heading\n\n## A section', {
    fileURL: new URL('file:///repo/docs/conditions.md'),
  });
  expect(nested.code).toContain('<h1');
  const withoutSource = await renderer.render('# A heading');
  expect(withoutSource.code).toContain('<h1');
});
