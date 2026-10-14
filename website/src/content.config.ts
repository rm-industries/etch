import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { defineCollection } from 'astro:content';

import { documentation, getDocumentationId } from './config/documentation';

export const collections = {
  docs: defineCollection({
    loader: glob({ base: '..', pattern: documentation.map((doc) => doc.source), generateId: getDocumentationId }),
    schema: z.object({
      title: z.string().min(1),
      description: z.string().min(1),
      publishedAt: z.coerce.date(),
      tags: z.array(z.string().min(1)).default([]),
      draft: z.boolean().default(false),
    }),
  }),
};
