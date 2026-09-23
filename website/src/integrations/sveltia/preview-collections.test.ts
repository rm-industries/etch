import { expect, test } from 'vitest';

import { docsContentModel } from '../../config/content-models/docs.ts';
import { previewCollectionNames } from './preview-collections.ts';

test('registers a preview for every collection that renders rich content', () => {
  expect(previewCollectionNames).toEqual([docsContentModel.name]);
});
