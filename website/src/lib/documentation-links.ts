import { posix, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import { satteri } from '@astrojs/markdown-satteri';

import { documentation } from '../config/documentation';
import { resolveSiteHref } from './paths';

const repository = 'https://github.com/rm-industries/etch/';
const publicPaths = new Map(documentation.map((doc) => [doc.source as string, doc.id as string]));

export const documentationHref = (href: string, source: string, base: string): string => {
  if (href.startsWith('#') || href.startsWith('/') || /^(?!https?:)[a-z]+:/iu.test(href)) return href;
  const sourcePrefix = `${repository}blob/main/`;
  if (/^https?:/u.test(href) && !href.startsWith(sourcePrefix)) return href;
  const local = href.startsWith(sourcePrefix)
    ? href.slice(sourcePrefix.length)
    : posix.join(posix.dirname(source), href);
  const url = new URL(local, 'https://repository.invalid/');
  const path = decodeURIComponent(url.pathname.slice(1));
  const id = publicPaths.get(path);
  if (id) return `${resolveSiteHref(`/docs/${id}/`, base)}${url.search}${url.hash}`;
  return `${repository}${path.endsWith('/') ? 'tree' : 'blob'}/main/${url.pathname.slice(1)}${url.search}${url.hash}`;
};

type MarkdownPlugin = Extract<ReturnType<typeof satteri>['options']['mdastPlugins'][number], { name: string }>;

export const documentationLinks =
  ({ root, base }: { root: string; base: string }) =>
  ({ fileURL }: { fileURL: URL | undefined }): MarkdownPlugin | false => {
    if (!fileURL) return false;
    const source = relative(root, fileURLToPath(fileURL)).replaceAll('\\', '/');
    return {
      name: 'documentation-links',
      heading(node, context) {
        if (node.depth === 1 && context.parent(node).type === 'root' && context.indexOf(node) === 0)
          context.removeNode(node);
      },
      link(node, context) {
        context.setProperty(node, 'url', documentationHref(node.url, source, base));
      },
      definition(node, context) {
        context.setProperty(node, 'url', documentationHref(node.url, source, base));
      },
    };
  };
