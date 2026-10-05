import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { defineCollection } from 'astro:content';

export const collections = {
  docs: defineCollection({
    loader: glob({ base: '../docs/guides', pattern: '**/*.md' }),
    schema: z.object({
      title: z.string().min(1),
      description: z.string().min(1),
      publishedAt: z.coerce.date(),
      tags: z.array(z.string().min(1)).default([]),
      draft: z.boolean().default(false),
    }),
  }),
};
