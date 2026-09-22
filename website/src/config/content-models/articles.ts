import { defineModel } from '@rm-industries/content-model';

export const articleContentModel = defineModel({
  name: 'articles',
  label: 'Articles',
  labelSingular: 'Article',
  folder: 'src/content/articles',
  extensions: ['md', 'mdx'],
  slug: '{{slug}}',
  sort: {
    fields: ['publishedAt', 'title'],
    default: { field: 'publishedAt', direction: 'descending' },
  },
  fields: {
    title: { kind: 'string', required: true, label: 'Title' },
    description: {
      kind: 'string',
      required: true,
      multiline: true,
      label: 'Description',
      help: 'A short summary used on listing pages and in social metadata.',
    },
    publishedAt: { kind: 'date', mode: 'date', required: true, label: 'Published at' },
    tags: {
      kind: 'list',
      default: [],
      items: { kind: 'string', required: true, label: 'Tag' },
      label: 'Tags',
      help: 'Use a few concise topics that help readers understand the article.',
    },
    draft: {
      kind: 'boolean',
      default: false,
      label: 'Draft',
      help: 'Draft articles appear locally but are excluded from production builds and feeds.',
    },
  },
  body: { name: 'body', label: 'Body', required: true },
});
