import { expect, test } from 'vitest';

import { articleContentModel } from '../../config/content-models/articles.ts';
import { sveltiaConfig } from './config.ts';

test('derives the article collection from the shared model', () => {
  expect(sveltiaConfig.collections.map(({ name }) => name)).toEqual([articleContentModel.name]);
  expect(sveltiaConfig.collections[0]?.fields.map(({ name }) => name)).toEqual([
    ...Object.keys(articleContentModel.fields),
    'body',
  ]);
});

test('keeps authentication credentials outside the configuration', () => {
  expect(sveltiaConfig.backend.name).toBe('github');
  expect('token' in sveltiaConfig.backend).toBe(false);
  expect(JSON.stringify(sveltiaConfig)).not.toContain('your-token');
});

test('exposes tags as a default-empty list derived from the article model', () => {
  const tags = sveltiaConfig.collections[0]?.fields.find(({ name }) => name === 'tags');

  expect(tags).toEqual({
    name: 'tags',
    label: 'Tags',
    after_input: 'Use a few concise topics that help readers understand the article.',
    required: false,
    widget: 'list',
    default: [],
  });
});

test('serializes the generated configuration', () => {
  expect(() => JSON.stringify(sveltiaConfig)).not.toThrow();
});
