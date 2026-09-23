import { getDeploymentConfig } from '../src/config/deployment';
import { site } from '../src/config/site';
import { resolveSiteHref } from '../src/lib/paths';

export const previewOrigin = 'http://127.0.0.1:4321';

const deployment = getDeploymentConfig(site.url);

export const resolvePreviewPath = (path: string): string => resolveSiteHref(path, deployment.base ?? '/');

export const resolvePreviewUrl = (path: string): string => new URL(resolvePreviewPath(path), previewOrigin).href;
