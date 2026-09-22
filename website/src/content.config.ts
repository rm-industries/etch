import { createAstroCollections } from '@rm-industries/content-model/astro';

import { contentModels } from './config/content-models/registry.ts';

export const collections = createAstroCollections(contentModels);
