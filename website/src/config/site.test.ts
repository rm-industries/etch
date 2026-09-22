import { expect, test } from 'vitest';

import { cmsBranding, defineSiteConfig, site, type SiteConfig } from './site.ts';

const validConfig = {
  name: 'Example site',
  description: 'An example site description.',
  author: 'Example Author',
  url: 'https://example.test',
  repository: 'example/site',
  language: 'en',
  socialImage: '/social-card.svg',
  navigation: [{ label: 'Home', href: '/' }],
  socialLinks: [],
} satisfies SiteConfig;

test('normalizes and freezes valid configuration', () => {
  const config = defineSiteConfig(validConfig);

  expect(config.url).toBe('https://example.test/');
  expect(Object.isFrozen(config)).toBe(true);
  expect(Object.isFrozen(config.navigation)).toBe(true);
});

test('rejects an empty site name', () => {
  expect(() => defineSiteConfig({ ...validConfig, name: '  ' })).toThrow(/name must not be empty/);
});

test('rejects a non-HTTP canonical URL', () => {
  expect(() => defineSiteConfig({ ...validConfig, url: 'file:///example' })).toThrow(
    /url must use the HTTP or HTTPS protocol/,
  );
});

test('rejects malformed canonical URLs and URL metadata', () => {
  expect(() => defineSiteConfig({ ...validConfig, url: 'relative' })).toThrow(/absolute URL/);
  expect(() => defineSiteConfig({ ...validConfig, url: 'https://user@example.test' })).toThrow(/credentials/);
  expect(() => defineSiteConfig({ ...validConfig, url: 'https://example.test?query=true' })).toThrow(/query/);
});

test('rejects control characters in optional text and invalid links', () => {
  expect(() => defineSiteConfig({ ...validConfig, author: 'Example\u0000Author' })).toThrow(/control characters/);
  expect(() => defineSiteConfig({ ...validConfig, navigation: [{ label: ' ', href: '/' }] })).toThrow(
    /navigation\[0\]\.label must not be empty/,
  );
});

test('derives CMS branding from the site name', () => {
  expect(cmsBranding.appTitle).toBe(`${site.name} Content Manager`);
});
