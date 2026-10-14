import { beforeEach, expect, test, vi } from 'vitest';

const { getCollection } = vi.hoisted(() => ({
  getCollection: vi.fn<(name: string, filter: (entry: Doc) => boolean) => Promise<Doc[]>>(),
}));

vi.mock('astro:content', () => ({ getCollection }));

import { getDocNeighbors, getDocs, type Doc } from './docs.ts';

const article = (id: string, publishedAt: string, draft = false) =>
  ({ id, data: { publishedAt: new Date(publishedAt), draft } }) as Doc;

beforeEach(() => {
  getCollection.mockReset();
});

test('filters drafts and follows the documented reading order', async () => {
  const entries = [
    article('modules-and-profiles', '2025-01-01'),
    article('facts', '2026-01-01', true),
    article('getting-started', '2025-06-01'),
  ];
  getCollection.mockImplementation(async (_name, filter: (entry: Doc) => boolean) => entries.filter(filter));

  await expect(getDocs()).resolves.toEqual([entries[2], entries[0]]);
  expect(getCollection).toHaveBeenCalledWith('docs', expect.any(Function));
});

test('can include drafts', async () => {
  const entries = [article('getting-started', '2025-01-01'), article('facts', '2026-01-01', true)];
  getCollection.mockImplementation(async (_name, filter: (entry: Doc) => boolean) => entries.filter(filter));

  await expect(getDocs({ includeDrafts: true })).resolves.toEqual([entries[0], entries[1]]);
});

test('returns previous and next neighbors without wrapping', () => {
  const entries = [article('newest', '2026-01-01'), article('middle', '2025-01-01'), article('oldest', '2024-01-01')];

  expect(getDocNeighbors('middle', entries)).toEqual({ previous: entries[0], next: entries[2] });
  expect(getDocNeighbors('newest', entries)).toEqual({ previous: undefined, next: entries[1] });
  expect(getDocNeighbors('missing', entries)).toEqual({});
});

test('excludes unlisted records even if an old collection cache contains them', async () => {
  const entries = [article('getting-started', '2025-01-01'), article('development', '2026-01-01')];
  getCollection.mockImplementation(async (_name, filter: (entry: Doc) => boolean) => entries.filter(filter));
  await expect(getDocs({ includeDrafts: true })).resolves.toEqual([entries[0]]);
});
