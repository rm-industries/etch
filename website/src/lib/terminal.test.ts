import { expect, test } from 'vitest';

import { terminalClasses, terminalCodeBlocks } from './terminal';

test('frames highlighted code while preserving syntax, attributes, and other content', () => {
  const root: Parameters<typeof terminalCodeBlocks.root>[0] = {
    type: 'root',
    children: [
      { type: 'text', value: '\n' },
      {
        type: 'element',
        tagName: 'pre',
        properties: { className: ['astro-code'], 'data-language': 'sh' },
        children: [
          { type: 'element', tagName: 'code', properties: {}, children: [{ type: 'text', value: './etch plan' }] },
        ],
      },
      { type: 'element', tagName: 'span', properties: {}, children: [{ type: 'text', value: 'caption' }] },
    ],
  };
  const [spacing, code, caption] = root.children;

  terminalCodeBlocks.root(root);

  expect(root.children[0]).toBe(spacing);
  expect(root.children[2]).toBe(caption);
  expect(root.children[1]).toMatchObject({
    tagName: 'div',
    properties: { className: [...terminalClasses.split(' '), 'not-prose', 'my-6'] },
    children: [code],
  });
  expect(root.children[1].type === 'element' && root.children[1].children[0]).toBe(code);
});
