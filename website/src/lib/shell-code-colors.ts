export const shellCodeColors = {
  name: 'etch:shell-code-colors',
  span(
    this: { options: { lang: string } },
    node: { children: Array<{ type: string; value?: string }>; properties?: { className?: string[] } },
    _line: number,
    col: number,
  ) {
    if (!['sh', 'bash', 'shell'].includes(this.options.lang)) return;
    const value = node.children.map((child) => child.value ?? '').join('');
    const kind = value.trimStart().startsWith('--')
      ? 'terminal-option'
      : col === 0 && !value.trimStart().startsWith('#')
        ? 'terminal-command'
        : 'terminal-argument';
    node.properties ??= {};
    node.properties.className = [...(node.properties.className ?? []), kind];
  },
};
