import type { MetadataRoute } from "next";

import { API_URL } from "@/lib/api";

export const revalidate = 3600;

interface JobList {
  items: { slug: string; updated_at?: string }[];
}

interface StartupList {
  id: string;
  slug: string;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${base}/`, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${base}/jobs`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${base}/startups`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${base}/companies-hiring`, lastModified: now, changeFrequency: "hourly", priority: 0.8 },
    { url: `${base}/industries`, lastModified: now, changeFrequency: "daily", priority: 0.7 },
    { url: `${base}/sources`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${base}/methodology`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
  ];

  const industrySlugs = [
    "artificial-intelligence",
    "machine-learning",
    "generative-ai",
    "saas",
    "fintech",
    "healthtech",
    "edtech",
    "deeptech",
    "robotics",
    "semiconductor",
    "enterprise-software",
    "cybersecurity",
    "blockchain",
    "ecommerce",
    "climatetech",
    "mobility",
    "manufacturing-technology",
    "developer-tools",
    "gaming",
  ];
  industrySlugs.forEach((slug) => {
    staticRoutes.push({
      url: `${base}/industries/${slug}`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.6,
    });
  });

  try {
    const jobsRes = await fetch(`${API_URL}/jobs?per_page=100&page=1`, {
      next: { revalidate: 3600 },
      headers: { Accept: "application/json" },
    });
    if (jobsRes.ok) {
      const data = (await jobsRes.json()) as JobList;
      for (const job of data.items ?? []) {
        staticRoutes.push({
          url: `${base}/jobs/${job.slug}`,
          lastModified: now,
          changeFrequency: "daily",
          priority: 0.7,
        });
      }
    }
  } catch {
    /* sitemap degrades gracefully */
  }

  try {
    const startupsRes = await fetch(`${API_URL}/startups?limit=100`, {
      next: { revalidate: 3600 },
      headers: { Accept: "application/json" },
    });
    if (startupsRes.ok) {
      const startups = (await startupsRes.json()) as StartupList[];
      for (const startup of startups ?? []) {
        staticRoutes.push({
          url: `${base}/startups/${startup.slug}`,
          lastModified: now,
          changeFrequency: "weekly",
          priority: 0.6,
        });
      }
    }
  } catch {
    /* ignore */
  }

  return staticRoutes;
}
