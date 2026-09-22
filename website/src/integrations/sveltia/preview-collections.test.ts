import { expect, test } from 'vitest';

import { articleContentModel } from '../../config/content-models/articles.ts';
import { previewCollectionNames } from './preview-collections.ts';

test('registers a preview for every collection that renders rich content', () => {
  expect(previewCollectionNames).toEqual([articleContentModel.name]);
});
