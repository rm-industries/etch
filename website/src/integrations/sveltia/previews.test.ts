import { expect, test, vi } from 'vitest';

vi.mock('@sveltia/cms', () => ({
  registerPreviewTemplate: vi.fn<(name: string, render: unknown) => void>(),
}));

import { registerSveltiaPreviews } from './previews.ts';

test('registers and renders the article preview', () => {
  const register = vi.fn<NonNullable<Parameters<typeof registerSveltiaPreviews>[0]>>();
  registerSveltiaPreviews(register);

  expect(register).toHaveBeenCalledOnce();
  const [name, render] = register.mock.calls[0] ?? [];
  const add = vi.fn<(first: string, second: string) => void>();
  const widgetFor = vi.fn<(name: string) => string>(() => 'rendered body');
  const result = render({ document: { body: { classList: { add } } }, widgetFor } as never);

  expect(name).toBe('articles');
  expect(add).toHaveBeenCalledWith('prose', 'mx-auto');
  expect(widgetFor).toHaveBeenCalledWith('body');
  expect(result).toBe('rendered body');
});
