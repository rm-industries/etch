import { createSveltiaCollection } from '@rm-industries/content-model/sveltia';
import type { CmsConfig } from '@sveltia/cms';

import { contentModels } from '../../config/content-models/registry.ts';
import { cmsBranding } from '../../config/site.ts';
import { resolveSiteHref } from '../../lib/paths.ts';

export const sveltiaConfig = {
  load_config_file: false,
  app_title: cmsBranding.appTitle,
  logo: { src: resolveSiteHref('/favicon.svg') },
  backend: {
    name: 'github',
    repo: 'your-github-user/your-repository',
    branch: 'main',
    auth_methods: ['token'],
    commit_messages: {
      create: 'content({{collection}}): create {{slug}}',
      update: 'content({{collection}}): update {{slug}}',
      delete: 'content({{collection}}): delete {{slug}}',
      uploadMedia: 'content(assets): upload {{path}}',
      deleteMedia: 'content(assets): delete {{path}}',
    },
  },
  media_folder: 'public/assets',
  public_folder: resolveSiteHref('/assets'),
  output: { omit_empty_optional_fields: true },
  collections: contentModels.map((model) => createSveltiaCollection(model)),
} satisfies CmsConfig;
