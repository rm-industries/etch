import { defineConfig, devices } from '@playwright/test';

const deploymentUrl = process.env.DEPLOYMENT_URL ?? 'https://deployment.invalid/';

export default defineConfig({
  testDir: './tests/smoke',
  outputDir: 'test-results/smoke',
  forbidOnly: true,
  retries: 2,
  reporter: process.env.GITLAB_CI
    ? [
        ['list'],
        ['junit', { outputFile: 'test-results/smoke.xml', includeProjectInTestName: true }],
        ['html', { open: 'never' }],
      ]
    : process.env.CI
      ? [['github'], ['html', { open: 'never' }]]
      : 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: deploymentUrl,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
