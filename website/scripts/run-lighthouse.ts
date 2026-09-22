import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

import { getDeploymentConfig } from '../src/config/deployment.ts';
import { site } from '../src/config/site.ts';
import { resolveSiteHref } from '../src/lib/paths.ts';

const previewOrigin = 'http://127.0.0.1:4321';
const auditedPaths = ['/', '/articles/', '/articles/getting-started/'] as const;

export const getLighthouseUrls = (siteUrl: string, origin = previewOrigin): string[] => {
  const deployment = getDeploymentConfig(siteUrl);

  return auditedPaths.map((path) => new URL(resolveSiteHref(path, deployment.base ?? '/'), origin).href);
};

export const runLighthouse = (): void => {
  const lighthouseCli = createRequire(import.meta.url).resolve('@lhci/cli/src/cli.js');
  const urlArguments = getLighthouseUrls(site.url).map((url) => `--collect.url=${url}`);
  const result = spawnSync(process.execPath, [lighthouseCli, 'autorun', ...urlArguments], {
    env: { ...process.env, ASTRO_PREVIEW_BACKGROUND: '0' },
    stdio: 'inherit',
  });

  if (result.error) throw result.error;
  if (result.status !== 0) process.exitCode = result.status ?? 1;
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) runLighthouse();
