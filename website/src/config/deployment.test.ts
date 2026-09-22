import { describe, expect, it } from 'vitest';

import { getDeploymentConfig } from './deployment';

describe('getDeploymentConfig', () => {
  it('configures a root deployment from an origin-only canonical URL', () => {
    expect(getDeploymentConfig('https://example.com/')).toEqual({ base: undefined, site: 'https://example.com' });
  });

  it('configures a project deployment from a canonical URL pathname', () => {
    expect(getDeploymentConfig('https://owner.github.io/project/')).toEqual({
      base: '/project',
      site: 'https://owner.github.io',
    });
  });
});
