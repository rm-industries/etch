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

test('matches the deployed project root exactly across trailing-slash variants', () => {
  for (const current of ['/etch', '/etch/', '/etch/?from=nav']) {
    expect(isCurrentPath(current, '/etch/', '/etch/')).toBe(true);
  }

  for (const current of ['/etch/docs', '/etch/docs/', '/etch/docs/getting-started/', '/etch/about/', '/etching/']) {
    expect(isCurrentPath(current, '/etch/', '/etch/')).toBe(false);
  }
});

test('keeps Docs nested and About scoped to its own segment at a project base', () => {
  for (const current of ['/etch/docs', '/etch/docs/', '/etch/docs/getting-started/']) {
    expect(isCurrentPath(current, '/etch/docs/', '/etch/')).toBe(true);
    expect(isCurrentPath(current, '/etch/about/', '/etch/')).toBe(false);
  }

  for (const current of ['/etch/about', '/etch/about/']) {
    expect(isCurrentPath(current, '/etch/about/', '/etch/')).toBe(true);
    expect(isCurrentPath(current, '/etch/docs/', '/etch/')).toBe(false);
  }

  expect(isCurrentPath('/etch/docs-summary/', '/etch/docs/', '/etch/')).toBe(false);
  expect(isCurrentPath('/etch/about-extra/', '/etch/about/', '/etch/')).toBe(false);
});

test('does not treat external URLs as current paths', () => {
  expect(isCurrentPath('/', 'https://example.com')).toBe(false);
  expect(isExternalHref('https://example.com')).toBe(true);
  expect(isExternalHref('/about/')).toBe(false);
});
