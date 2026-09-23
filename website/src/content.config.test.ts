import { expect, test, vi } from 'vitest';

import { contentModels } from './config/content-models/registry.ts';
import { collections } from './content.config.ts';

test('registers every shared model with the Astro adapter', () => {
  expect(Object.keys(collections)).toEqual(contentModels.map((model) => model.name));
});

test('validates public guide metadata and defaults', () => {
  const schemaFactory = collections.docs.schema;
  if (typeof schemaFactory !== 'function') throw new Error('Expected a schema factory');
  const schema = schemaFactory({ image: vi.fn() });
  expect(
    schema.parse({
      title: 'A guide',
      description: 'A public Etch guide',
      publishedAt: '2026-09-22',
    }),
  ).toMatchObject({ tags: [], draft: false });
  expect(schema.safeParse({ title: 'Missing metadata' }).success).toBe(false);
});
