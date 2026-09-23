import { readFile } from 'node:fs/promises';

import { describe, expect, it } from 'vitest';

describe('documentation examples', () => {
  it('does not duplicate the article title as a Markdown heading', async () => {
    const guide = await readFile(new URL('../docs/guides/content-and-cms.md', import.meta.url), 'utf8');
    const articleExample = /```md\n([\s\S]*?)\n```/u.exec(guide)?.[1];

    expect(articleExample).toContain('title: My first article');
    expect(articleExample).not.toMatch(/^# /mu);
  });
});
