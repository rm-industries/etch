import { readdir, readFile, stat } from 'node:fs/promises';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const requiredOutputPaths = [
  '404.html',
  'about/index.html',
  'admin/index.html',
  'articles/facts-and-providers/index.html',
  'articles/modules-and-profiles/index.html',
  'articles/getting-started/index.html',
  'articles/index.html',
  'index.html',
  'robots.txt',
  'rss.xml',
  'site.webmanifest',
  'sitemap-index.xml',
] as const;

const forbiddenOutputPatterns = [/__FORGE_[A-Z0-9_]+__/u, /FORGE_[A-Z0-9_]+_PLACEHOLDER/u] as const;

const listFiles = async (directory: string, root = directory): Promise<string[]> => {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await listFiles(path, root)));
    if (entry.isFile()) files.push(relative(root, path));
  }

  return files;
};

export const validateBuild = async (outputDirectory: string) => {
  const output = resolve(outputDirectory);
  if (!(await stat(output).catch(() => undefined))?.isDirectory()) {
    throw new Error(`Build output directory does not exist: ${output}`);
  }

  const files = await listFiles(output);
  const missingPaths = requiredOutputPaths.filter((path) => !files.includes(path));
  if (missingPaths.length > 0) {
    throw new Error(`Build output is missing required paths:\n${missingPaths.join('\n')}`);
  }

  for (const path of files) {
    const content = await readFile(join(output, path), 'utf8').catch(() => undefined);
    if (content === undefined || content.includes('\0')) continue;

    for (const pattern of forbiddenOutputPatterns) {
      const match = content.match(pattern);
      if (match) throw new Error(`Build output contains forbidden text in ${path}: ${match[0]}`);
    }
  }
};

const isEntryPoint = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isEntryPoint) {
  const projectDirectory = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  await validateBuild(join(projectDirectory, 'dist'));
  console.log(`Validated ${requiredOutputPaths.length} required build outputs and scanned generated text.`);
}
