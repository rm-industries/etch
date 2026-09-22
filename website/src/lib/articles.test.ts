import { beforeEach, expect, test, vi } from 'vitest';

const { getCollection } = vi.hoisted(() => ({
  getCollection: vi.fn<(name: string, filter: (entry: Article) => boolean) => Promise<Article[]>>(),
}));

vi.mock('astro:content', () => ({ getCollection }));

import { getArticleNeighbors, getArticles, type Article } from './articles.ts';

const article = (id: string, publishedAt: string, draft = false) =>
  ({ id, data: { publishedAt: new Date(publishedAt), draft } }) as Article;

beforeEach(() => {
  getCollection.mockReset();
});

test('filters drafts and sorts published articles newest first', async () => {
  const entries = [
    article('older', '2025-01-01'),
    article('draft', '2026-01-01', true),
    article('newer', '2025-06-01'),
  ];
  getCollection.mockImplementation(async (_name, filter: (entry: Article) => boolean) => entries.filter(filter));

  await expect(getArticles()).resolves.toEqual([entries[2], entries[0]]);
  expect(getCollection).toHaveBeenCalledWith('articles', expect.any(Function));
});

test('can include drafts', async () => {
  const entries = [article('published', '2025-01-01'), article('draft', '2026-01-01', true)];
  getCollection.mockImplementation(async (_name, filter: (entry: Article) => boolean) => entries.filter(filter));

  await expect(getArticles({ includeDrafts: true })).resolves.toEqual([entries[1], entries[0]]);
});

test('returns previous and next neighbors without wrapping', () => {
  const entries = [article('newest', '2026-01-01'), article('middle', '2025-01-01'), article('oldest', '2024-01-01')];

  expect(getArticleNeighbors('middle', entries)).toEqual({ previous: entries[2], next: entries[0] });
  expect(getArticleNeighbors('newest', entries)).toEqual({ previous: entries[1], next: undefined });
  expect(getArticleNeighbors('missing', entries)).toEqual({});
});
