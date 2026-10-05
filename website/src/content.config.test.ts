import { expect, test } from 'vitest';

import { collections } from './content.config.ts';

test('validates public guide metadata and defaults', () => {
  const schema = collections.docs.schema;
  if (!schema || typeof schema === 'function') throw new Error('Expected a native schema');
  expect(
    schema.parse({
      title: 'A guide',
      description: 'A public Etch guide',
      publishedAt: '2026-09-22',
    }),
  ).toMatchObject({ tags: [], draft: false });
  expect(schema.safeParse({ title: 'Missing metadata' }).success).toBe(false);
  expect(schema.safeParse({ title: '', description: 'A guide', publishedAt: 'invalid' }).success).toBe(false);
});
