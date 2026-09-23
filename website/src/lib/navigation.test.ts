import { expect, test } from 'vitest';

import { isCurrentPath, isExternalHref } from './navigation.ts';

test('matches exact and nested navigation paths at segment boundaries', () => {
  expect(isCurrentPath('/docs/', '/docs')).toBe(true);
  expect(isCurrentPath('docs/?page=2', '/docs/#content')).toBe(true);
  expect(isCurrentPath('/docs/example/', '/docs/')).toBe(true);
  expect(isCurrentPath('/docs-summary/', '/docs')).toBe(false);
});

test('matches the home route only at the site root', () => {
  expect(isCurrentPath('/', '/')).toBe(true);
  expect(isCurrentPath('', '/')).toBe(true);
  expect(isCurrentPath('/docs/', '/')).toBe(false);
});

test('does not treat external URLs as current paths', () => {
  expect(isCurrentPath('/', 'https://example.com')).toBe(false);
  expect(isExternalHref('https://example.com')).toBe(true);
  expect(isExternalHref('/about/')).toBe(false);
});
