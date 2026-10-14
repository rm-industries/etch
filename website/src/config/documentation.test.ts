import { expect, test } from 'vitest';

import { documentation, getDocumentationEntry, getDocumentationId } from './documentation';

test('curates user docs with unique routes and sources, preserving existing guide routes', () => {
  expect(getDocumentationId({ entry: 'docs/guides/getting-started.md' })).toBe('getting-started');
  expect(getDocumentationEntry('cli')?.section).toBe('Configuration and commands');
  expect(new Set(documentation.map((doc) => doc.id)).size).toBe(documentation.length);
  expect(new Set(documentation.map((doc) => doc.source)).size).toBe(documentation.length);
  expect(getDocumentationEntry('missing')).toBeUndefined();
  expect(() => getDocumentationId({ entry: 'docs/development.md' })).toThrow('not in the public collection');
  expect(() => getDocumentationId({ entry: 'docs/performance-review.md' })).toThrow('not in the public collection');
});
