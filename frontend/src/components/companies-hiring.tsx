"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { statsApi } from "@/lib/api";

export function CompaniesHiring() {
  const [industry, setIndustry] = React.useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["companies-hiring", industry],
    queryFn: async () => {
      const [hiring, industries] = await Promise.all([statsApi.hiring(), statsApi.industries()]);
      return { hiring, industries };
    },
  });

  const companies = (data?.hiring?.companies ?? []).filter((company) =>
    industry ? company.industry === industry : true,
  );

  const industryOptions = [
    { value: "", label: "All industries" },
    ...(data?.industries?.industries ?? []).map((row) => ({
      value: row.industry,
      label: `${row.industry} (${row.count})`,
    })),
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            <Building2 className="size-6 text-primary" />
            Companies hiring now
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Companies with at least one active opening in our Ahmedabad &amp; Gujarat coverage, ranked by
            the number of roles they have open right now.
          </p>
        </div>
        <Select
          options={industryOptions}
          value={industry}
          onValueChange={setIndustry}
          className="w-full sm:w-64"
          placeholder="All industries"
        />
      </div>

      <div className="mt-8">
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Card key={index} className="h-40 animate-pulse" />
            ))}
          </div>
        ) : companies.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {companies.map((company) => (
              <Card key={company.startup_id ?? company.name} className="transition-all hover:border-primary/40 hover:shadow-md">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      {company.slug ? (
                        <Link
                          href={`/startups/${company.slug}`}
                          className="truncate text-sm font-semibold tracking-tight hover:text-primary"
                        >
                          {company.name}
                        </Link>
                      ) : (
                        <span className="truncate text-sm font-semibold tracking-tight">{company.name}</span>
                      )}
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {company.industry ?? "Technology"}
                      </p>
                    </div>
                    <Badge variant="default">{company.openings} open</Badge>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-border/70 pt-3">
                    <Link
                      href={`/jobs?company=${encodeURIComponent(company.name)}`}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                    >
                      View openings <ExternalLink className="size-3" />
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="p-12 text-center text-sm text-muted-foreground">
            No companies with active openings yet. Run the discovery pipeline to populate this list.
          </Card>
        )}
      </div>
    </div>
  );
}
