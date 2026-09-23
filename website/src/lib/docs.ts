import { getCollection, type CollectionEntry } from 'astro:content';

export type Doc = CollectionEntry<'docs'>;

const sortDocs = (entries: readonly Doc[]): Doc[] =>
  [...entries].sort((left, right) => right.data.publishedAt.getTime() - left.data.publishedAt.getTime());

export const getDocs = async ({ includeDrafts = false }: { includeDrafts?: boolean } = {}): Promise<Doc[]> =>
  sortDocs(await getCollection('docs', ({ data }) => includeDrafts || !data.draft));

export const getDocNeighbors = (id: string, entries: readonly Doc[]) => {
  const index = entries.findIndex((entry) => entry.id === id);

  if (index < 0) return {};

  return {
    previous: entries[index + 1],
    next: entries[index - 1],
  };
};
