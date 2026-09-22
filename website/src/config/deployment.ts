export interface DeploymentConfig {
  base: string | undefined;
  site: string;
}

/** Derive Astro's origin and optional project path from the canonical site URL. */
export const getDeploymentConfig = (siteUrl: string): DeploymentConfig => {
  const canonicalUrl = new URL(siteUrl);

  return {
    base: canonicalUrl.pathname === '/' ? undefined : canonicalUrl.pathname.replace(/\/$/, ''),
    site: canonicalUrl.origin,
  };
};
