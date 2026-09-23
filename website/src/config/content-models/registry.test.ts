import { defineModels } from '@rm-industries/content-model';
import { expect, test } from 'vitest';

import { docsContentModel } from './docs.ts';
import { contentModels } from './registry.ts';

test('registers the shared article model', () => {
  expect(contentModels).toEqual([docsContentModel]);
  expect(contentModels[0]?.fields.tags).toMatchObject({ kind: 'list', default: [] });
});

test('rejects duplicate model names', () => {
  expect(() => defineModels([docsContentModel, docsContentModel])).toThrow(/duplicate collection name/i);
});
