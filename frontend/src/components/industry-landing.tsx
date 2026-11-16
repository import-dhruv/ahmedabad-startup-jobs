"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobCard } from "@/components/job-card";
import { jobsApi } from "@/lib/api";

export function IndustryLanding({
  slug,
  title,
  total,
}: {
  slug: string;
  title: string;
  total: number;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["industry", slug],
    queryFn: () => jobsApi.search({ industry: [title], per_page: 25 }),
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="border-b border-border pb-6">
        <Badge variant="accent" className="mb-3 gap-1.5">
          <Sparkles className="size-3" /> Industry
        </Badge>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {title} startup jobs in Ahmedabad
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          {total} open {total === 1 ? "role" : "roles"} at {title} startups across Ahmedabad,
          Gandhinagar, GIFT City and the wider Gujarat ecosystem — each with its original posting and a
          direct application link.
        </p>
      </div>

      <div className="mt-8 grid gap-3 lg:grid-cols-2">
        {isLoading ? (
          <>
            <Card className="h-40 animate-pulse" />
            <Card className="h-40 animate-pulse" />
          </>
        ) : data?.items?.length ? (
          data.items.map((job) => <JobCard key={job.id} job={job} />)
        ) : (
          <Card className="p-12 text-center text-sm text-muted-foreground lg:col-span-2">
            No {title.toLowerCase()} openings are open right now. Try browsing{" "}
            <Link href="/jobs" className="text-primary hover:underline">
              all openings
            </Link>{" "}
            or view{" "}
            <Link href="/companies-hiring" className="text-primary hover:underline">
              companies hiring
            </Link>
            .
          </Card>
        )}
      </div>

      <div className="mt-10 flex flex-wrap gap-3">
        <Button asChild variant="outline">
          <Link href="/jobs">
            Browse all jobs <ArrowRight className="size-4" />
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/industries">All industries</Link>
        </Button>
      </div>
    </div>
  );
}
