import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import { afterEach, describe, expect, test } from 'vitest';

import { validateBuild } from './validate-build';

const requiredPaths = [
  '404.html',
  'about/index.html',
  'admin/index.html',
  'docs/facts-and-providers/index.html',
  'docs/modules-and-profiles/index.html',
  'docs/getting-started/index.html',
  'docs/index.html',
  'index.html',
  'robots.txt',
  'rss.xml',
  'site.webmanifest',
  'sitemap-index.xml',
] as const;

const fixtures: string[] = [];

const createFixture = async () => {
  const fixture = await mkdtemp(join(tmpdir(), 'forge-build-output-'));
  fixtures.push(fixture);
  for (const path of requiredPaths) {
    const output = join(fixture, path);
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, path.endsWith('.html') ? '<!doctype html><main>Forge</main>' : 'Forge\n');
  }
  return fixture;
};

afterEach(async () => {
  await Promise.all(fixtures.splice(0).map((fixture) => rm(fixture, { recursive: true, force: true })));
});

describe('generated build validation', () => {
  test('accepts the complete neutral output fixture', async () => {
    await expect(validateBuild(await createFixture())).resolves.toBeUndefined();
  });

  test('reports a missing required output path', async () => {
    const fixture = await createFixture();
    await rm(join(fixture, 'rss.xml'));
    await expect(validateBuild(fixture)).rejects.toThrow('rss.xml');
  });

  test('rejects unresolved generator tokens', async () => {
    const fixture = await createFixture();
    const unresolvedToken = '__FORGE_' + 'SITE_NAME__';
    await writeFile(join(fixture, 'index.html'), `<p>${unresolvedToken}</p>`);
    await expect(validateBuild(fixture)).rejects.toThrow(unresolvedToken);
  });
});
