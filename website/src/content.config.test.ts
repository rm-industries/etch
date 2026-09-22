import { expect, test } from 'vitest';

import { contentModels } from './config/content-models/registry.ts';
import { collections } from './content.config.ts';

test('registers every shared model with the Astro adapter', () => {
  expect(Object.keys(collections)).toEqual(contentModels.map((model) => model.name));
});
