import { createAstroSchema } from '@rm-industries/content-model/astro';
import { glob } from 'astro/loaders';
import { defineCollection } from 'astro:content';

import { docsContentModel } from './config/content-models/docs.ts';

export const collections = {
  docs: defineCollection({
    loader: glob({ base: '../docs/guides', pattern: '**/*.md' }),
    schema: (context) => createAstroSchema(docsContentModel, context),
  }),
};
