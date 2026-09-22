import { defineModels } from '@rm-industries/content-model';
import { expect, test } from 'vitest';

import { articleContentModel } from './articles.ts';
import { contentModels } from './registry.ts';

test('registers the shared article model', () => {
  expect(contentModels).toEqual([articleContentModel]);
  expect(contentModels[0]?.fields.tags).toMatchObject({ kind: 'list', default: [] });
});

test('rejects duplicate model names', () => {
  expect(() => defineModels([articleContentModel, articleContentModel])).toThrow(/duplicate collection name/i);
});
