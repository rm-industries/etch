import { getCollection, type CollectionEntry } from 'astro:content';

export type Article = CollectionEntry<'articles'>;

const sortArticles = (entries: readonly Article[]): Article[] =>
  [...entries].sort((left, right) => right.data.publishedAt.getTime() - left.data.publishedAt.getTime());

export const getArticles = async ({ includeDrafts = false }: { includeDrafts?: boolean } = {}): Promise<Article[]> =>
  sortArticles(await getCollection('articles', ({ data }) => includeDrafts || !data.draft));

export const getArticleNeighbors = (id: string, entries: readonly Article[]) => {
  const index = entries.findIndex((entry) => entry.id === id);

  if (index < 0) return {};

  return {
    previous: entries[index + 1],
    next: entries[index - 1],
  };
};
