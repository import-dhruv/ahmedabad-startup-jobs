import type { Metadata } from "next";
import Link from "next/link";
import { Database, ExternalLink, Radio } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { API_URL } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Data sources & transparency",
  description:
    "Every source this platform reads, with the connector type, last successful sync and how many live openings it contributes.",
  alternates: { canonical: "/sources" },
};

export const revalidate = 120;

interface SourceStat {
  id: string;
  name: string;
  slug: string;
  connector_type: string;
  last_success_at: string | null;
  active_jobs: number;
}

export default async function SourcesPage() {
  let sources: SourceStat[] = [];
  let totalJobs = 0;
  try {
    const res = await fetch(`${API_URL}/sources/stats`, {
      next: { revalidate: 120 },
      headers: { Accept: "application/json" },
    });
    if (res.ok) sources = (await res.json()) as SourceStat[];
  } catch {
    sources = [];
  }

  totalJobs = sources.reduce((sum, source) => sum + (source.active_jobs ?? 0), 0);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="border-b border-border pb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          <Database className="size-6 text-primary" />
          Data sources &amp; transparency
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          This platform only reads publicly accessible endpoints and pages that permit automated access.
          Each listing keeps a link to the exact page it came from, and we never create a posting that an
          employer has not published.
        </p>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Card>
          <CardContent className="p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Sources connected</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight">{sources.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Live openings</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight">{totalJobs}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Refresh cadence</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight">15 min</p>
            <p className="mt-1 text-xs text-muted-foreground">Connected job-board APIs</p>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-5 py-3 font-medium">Source</th>
                  <th className="px-5 py-3 font-medium">Connector</th>
                  <th className="px-5 py-3 font-medium">Active openings</th>
                  <th className="px-5 py-3 font-medium">Last sync</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-3 font-medium">{source.name}</td>
                    <td className="px-5 py-3">
                      <Badge variant="secondary">{source.connector_type}</Badge>
                    </td>
                    <td className="px-5 py-3">{source.active_jobs}</td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {source.last_success_at ? formatDate(source.last_success_at) : "Not yet synced"}
                    </td>
                  </tr>
                ))}
                {sources.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted-foreground">
                      No sources registered yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardContent className="p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Radio className="size-4 text-primary" /> How listings are verified
            </h2>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>Every listing stores the exact URL it was read from.</li>
              <li>Application links are re-checked on a daily schedule.</li>
              <li>Listings that stop appearing are marked stale, then expired.</li>
              <li>Duplicates across sources are merged, keeping every source reference.</li>
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold">Our rules</h2>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>We respect robots.txt and publish a descriptive user agent.</li>
              <li>We never fabricate companies, roles or salary ranges.</li>
              <li>AI-generated summaries are labelled as summaries.</li>
              <li>Company headquarters is tracked separately from job location.</li>
            </ul>
            <Link
              href="/methodology"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              Read the full methodology <ExternalLink className="size-3" />
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
