import type { ShikiConfig } from 'astro';

export const terminalClasses = 'terminal mockup-code w-full min-w-0 bg-base-300 text-base-content shadow-xl';

export const terminalCodeBlocks = {
  name: 'etch:terminal-code-blocks',
  root(this: void, node) {
    node.children = node.children.map((child) =>
      child.type === 'element' && child.tagName === 'pre'
        ? {
            type: 'element',
            tagName: 'div',
            properties: { className: [...terminalClasses.split(' '), 'not-prose', 'my-6'] },
            children: [child],
          }
        : child,
    );
  },
} satisfies NonNullable<ShikiConfig['transformers']>[number];
