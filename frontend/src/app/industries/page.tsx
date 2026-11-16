import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { API_SERVER_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "Industries",
  description:
    "Startup hiring by industry across Ahmedabad and Gujarat — see which sectors are opening the most roles.",
  alternates: { canonical: "/industries" },
};

export const revalidate = 300;

async function fetchIndustries() {
  try {
    const res = await fetch(`${API_SERVER_URL}/stats/industries`, {
      next: { revalidate: 300 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as {
      industries: { industry: string; count: number; companies: number }[];
    };
  } catch {
    return null;
  }
}

export default async function IndustriesPage() {
  const data = await fetchIndustries();
  const industries = data?.industries ?? [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="border-b border-border pb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          <Sparkles className="size-6 text-primary" />
          Industries
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Where startup hiring is concentrated in the Ahmedabad ecosystem, measured from active openings
          linked to companies in our directory.
        </p>
      </div>

      {industries.length ? (
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {industries.map((industry) => {
            const slug = industry.industry.toLowerCase().replace(/[^a-z0-9]+/g, "-");
            const max = industries[0]?.count || 1;
            return (
              <Link key={industry.industry} href={`/industries/${slug}`}>
                <Card className="h-full transition-all hover:border-primary/40 hover:shadow-md">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="truncate text-sm font-semibold tracking-tight">{industry.industry}</h2>
                      <Badge variant="secondary">{industry.count}</Badge>
                    </div>
                    <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary/70"
                        style={{ width: `${Math.max((industry.count / max) * 100, 6)}%` }}
                      />
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">
                      {industry.companies} compan{industry.companies === 1 ? "y" : "ies"} hiring
                    </p>
                    <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary">
                      View openings <ArrowRight className="size-3" />
                    </span>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      ) : (
        <Card className="mt-8 p-12 text-center text-sm text-muted-foreground">
          Industry data appears once companies are linked to their openings.
        </Card>
      )}
    </div>
  );
}
