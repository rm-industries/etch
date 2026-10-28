/** Public user documentation, in reading order. Maintainer records are not published. */
export const documentation = [
  { id: 'getting-started', source: 'docs/guides/getting-started.md', section: 'Start here' },
  { id: 'modules-and-profiles', source: 'docs/guides/modules-and-profiles.md', section: 'Start here' },
  { id: 'user-guide', source: 'docs/guides/user-guide.md', section: 'Start here' },
  { id: 'migrating-from-dotbot', source: 'docs/guides/migrating-from-dotbot.md', section: 'Start here' },
  { id: 'developer-profile', source: 'docs/developer-profile.md', section: 'Start here' },
  { id: 'cli', source: 'docs/cli.md', section: 'Configuration and commands' },
  { id: 'configuration', source: 'docs/configuration.md', section: 'Configuration and commands' },
  { id: 'facts-and-providers', source: 'docs/guides/facts-and-providers.md', section: 'Configuration and commands' },
  { id: 'facts', source: 'docs/facts.md', section: 'Configuration and commands' },
  { id: 'conditions', source: 'docs/conditions.md', section: 'Configuration and commands' },
  { id: 'versions', source: 'docs/versions.md', section: 'Configuration and commands' },
  { id: 'filesystem', source: 'docs/filesystem.md', section: 'Actions and plugins' },
  { id: 'clean', source: 'docs/clean.md', section: 'Actions and plugins' },
  { id: 'commands', source: 'docs/commands.md', section: 'Actions and plugins' },
  { id: 'installers', source: 'docs/installers.md', section: 'Actions and plugins' },
  { id: 'downloads', source: 'docs/downloads.md', section: 'Actions and plugins' },
  { id: 'plugins', source: 'docs/plugins.md', section: 'Actions and plugins' },
  { id: 'npm', source: 'plugins/npm/README.md', section: 'Actions and plugins' },
  { id: 'homebrew', source: 'plugins/homebrew/README.md', section: 'Actions and plugins' },
  { id: 'claude', source: 'plugins/claude/README.md', section: 'Actions and plugins' },
  { id: 'codex', source: 'plugins/codex/README.md', section: 'Actions and plugins' },
  { id: 'vscode', source: 'plugins/vscode/README.md', section: 'Actions and plugins' },
  { id: 'macos-defaults', source: 'plugins/macos_defaults/README.md', section: 'Actions and plugins' },
  { id: 'windows-registry', source: 'plugins/windows_registry/README.md', section: 'Actions and plugins' },
  { id: 'planning', source: 'docs/planning.md', section: 'Running and maintaining your setup' },
  { id: 'applying', source: 'docs/applying.md', section: 'Running and maintaining your setup' },
  { id: 'scheduling', source: 'docs/scheduling.md', section: 'Running and maintaining your setup' },
  { id: 'diagnostics', source: 'docs/diagnostics.md', section: 'Running and maintaining your setup' },
  { id: 'submodules', source: 'docs/submodules.md', section: 'Running and maintaining your setup' },
  { id: 'importing', source: 'docs/importing.md', section: 'Running and maintaining your setup' },
  { id: 'ownership', source: 'docs/ownership.md', section: 'Running and maintaining your setup' },
  { id: 'compatibility', source: 'docs/compatibility.md', section: 'Running and maintaining your setup' },
  { id: 'windows', source: 'docs/windows.md', section: 'Running and maintaining your setup' },
  { id: 'architecture', source: 'docs/guides/architecture.md', section: 'Running and maintaining your setup' },
] as const;

const entries = new Map(documentation.map((doc, order) => [doc.id, { ...doc, order }]));
const sources = new Map(documentation.map((doc) => [doc.source, doc.id]));

export const getDocumentationEntry = (id: string) => entries.get(id as (typeof documentation)[number]['id']);
export const getDocumentationId = ({ entry: source }: { entry: string }): string => {
  const id = sources.get(source as (typeof documentation)[number]['source']);
  if (!id) throw new Error(`Document is not in the public collection: ${source}`);
  return id;
};
