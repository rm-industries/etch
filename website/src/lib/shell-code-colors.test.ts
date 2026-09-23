import { expect, test } from 'vitest';

import { shellCodeColors } from './shell-code-colors';

test('colors shell commands, options, and arguments without recoloring other languages', () => {
  for (const [value, column, expected] of [
    ['./etch', 0, 'terminal-command'],
    [' --profile', 1, 'terminal-option'],
    [' developer', 2, 'terminal-argument'],
    ['# a comment', 0, 'terminal-argument'],
  ] as const) {
    const node = { children: [{ type: 'text', value }] };
    shellCodeColors.span.call({ options: { lang: 'sh' } }, node, 0, column);
    expect(node).toMatchObject({ properties: { className: [expected] } });
  }

  const existing = { children: [{ type: 'text' }], properties: { className: ['existing'] } };
  shellCodeColors.span.call({ options: { lang: 'bash' } }, existing, 0, 1);
  expect(existing.properties.className).toEqual(['existing', 'terminal-argument']);

  const typescript = { children: [{ type: 'text', value: 'const' }] };
  shellCodeColors.span.call({ options: { lang: 'ts' } }, typescript, 0, 0);
  expect(typescript).not.toHaveProperty('properties');
});
