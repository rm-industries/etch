import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { documentation } from '../src/config/documentation.ts';

const mode = process.argv[2];
if (mode !== 'markdown' && mode !== 'spelling') throw new Error('Choose markdown or spelling.');
const binary =
  mode === 'markdown' ? '../node_modules/markdownlint-cli/markdownlint.js' : '../node_modules/cspell/bin.mjs';
const result = spawnSync(
  process.execPath,
  [fileURLToPath(new URL(binary, import.meta.url)), ...documentation.map((doc) => `../${doc.source}`)],
  { cwd: fileURLToPath(new URL('../', import.meta.url)), stdio: 'inherit' },
);
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
