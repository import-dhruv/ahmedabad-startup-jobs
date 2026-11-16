"use client";

import * as React from "react";
import Link from "next/link";
import { Building2, ExternalLink, MapPin, ShieldCheck, ShieldQuestion, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { JobSummary } from "@/lib/api";
import { cn, formatCurrency, GEO_SCOPE_LABEL, timeAgo, VERIFICATION_LABEL } from "@/lib/utils";

function CompanyLogo({
  name,
  logoUrl,
  className,
}: {
  name: string;
  logoUrl: string | null;
  className?: string;
}) {
  const [failed, setFailed] = React.useState(false);
  if (logoUrl && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={logoUrl}
        alt={`${name} logo`}
        onError={() => setFailed(true)}
        className={cn("size-11 shrink-0 rounded-lg border border-border bg-background object-contain p-1", className)}
      />
    );
  }
  return (
    <span
      className={cn(
        "flex size-11 shrink-0 items-center justify-center rounded-lg border border-border bg-muted text-xs font-semibold text-muted-foreground",
        className,
      )}
    >
      {name.slice(0, 2).toUpperCase()}
    </span>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  if (status === "verified") {
    return (
      <Badge variant="success" className="gap-1">
        <ShieldCheck className="size-3" /> {VERIFICATION_LABEL[status] ?? status}
      </Badge>
    );
  }
  if (status === "stale") {
    return (
      <Badge variant="warning" className="gap-1">
        <ShieldQuestion className="size-3" /> Needs re-check
      </Badge>
    );
  }
  if (status === "expired" || status === "rejected") {
    return <Badge variant="destructive">{VERIFICATION_LABEL[status] ?? status}</Badge>;
  }
  return <Badge variant="outline">Unverified</Badge>;
}

export function JobCard({ job, compact = false }: { job: JobSummary; compact?: boolean }) {
  const salary = formatCurrency(job.salary.max ?? job.salary.min, job.salary.currency, job.salary.period);
  const locationLabel =
    job.location.city ??
    (job.location.raw?.split(",")[0]?.trim() || GEO_SCOPE_LABEL[job.geo_scope] || "Location flexible");
  const posted = job.posted_at ?? job.discovered_at;

  return (
    <article className="group relative rounded-xl border border-border bg-card p-4 transition-all duration-200 hover:border-primary/40 hover:shadow-md sm:p-5">
      <div className="flex gap-4">
        <CompanyLogo name={job.company.name} logoUrl={job.company.logo_url} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
            <div className="min-w-0">
              <Link
                href={`/jobs/${job.slug}`}
                className="line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight transition-colors hover:text-primary"
              >
                {job.title}
              </Link>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
                {job.company.slug ? (
                  <Link
                    href={`/startups/${job.company.slug}`}
                    className="font-medium text-foreground/80 transition-colors hover:text-primary"
                  >
                    {job.company.name}
                  </Link>
                ) : (
                  <span className="font-medium text-foreground/80">{job.company.name}</span>
                )}
                {job.company.industry ? (
                  <>
                    <span aria-hidden>·</span>
                    <span className="truncate">{job.company.industry}</span>
                  </>
                ) : null}
              </div>
            </div>

            {salary ? (
              <span className="shrink-0 rounded-md bg-success/10 px-2 py-1 text-xs font-semibold text-success">
                {salary}
              </span>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary" className="gap-1">
              <MapPin className="size-3" /> {locationLabel}
            </Badge>
            {job.employment_type ? <Badge variant="secondary">{job.employment_type}</Badge> : null}
            {job.work_arrangement ? <Badge variant="secondary">{job.work_arrangement}</Badge> : null}
            {job.experience_level ? <Badge variant="outline">{job.experience_level}</Badge> : null}
            {job.is_remote ? (
              <Badge variant="accent" className="gap-1">
                <Sparkles className="size-3" /> Remote
              </Badge>
            ) : null}
            {job.categories?.[0] && job.categories[0] !== "Internship" ? (
              <Badge variant="outline">{job.categories[0]}</Badge>
            ) : null}
            {job.categories?.includes("Internship") ? (
              <Badge variant="accent">Internship</Badge>
            ) : null}
          </div>

          {!compact && job.skills?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {job.skills.slice(0, 6).map((skill) => (
                <span
                  key={skill}
                  className="rounded border border-border/70 px-1.5 py-0.5 text-[11px] text-muted-foreground"
                >
                  {skill}
                </span>
              ))}
              {job.skills.length > 6 ? (
                <span className="px-1 py-0.5 text-[11px] text-muted-foreground">
                  +{job.skills.length - 6} more
                </span>
              ) : null}
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/70 pt-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <VerificationBadge status={job.verification_status} />
              <span>Posted {timeAgo(posted)}</span>
              {job.source ? (
                <span className="inline-flex items-center gap-1">
                  via {job.source.name}
                </span>
              ) : null}
            </div>

            <Button asChild size="sm" variant="outline" className="gap-1.5">
              <a href={job.apply_url} target="_blank" rel="noopener noreferrer nofollow">
                Apply <ExternalLink className="size-3.5" />
              </a>
            </Button>
          </div>
        </div>
      </div>
    </article>
  );
}

export function CompanyAvatar({ name, logoUrl }: { name: string; logoUrl: string | null }) {
  return <CompanyLogo name={name} logoUrl={logoUrl} className="size-10 rounded-lg" />;
}

export function StartupCard({
  startup,
}: {
  startup: {
    id: string;
    name: string;
    slug: string;
    logo_url: string | null;
    website: string | null;
    industry: string;
    hq_city: string | null;
    active_job_count: number;
    description?: string | null;
  };
}) {
  return (
    <Link
      href={`/startups/${startup.slug}`}
      className="group flex flex-col rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/40 hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <CompanyLogo name={startup.name} logoUrl={startup.logo_url} />
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold tracking-tight group-hover:text-primary">
            {startup.name}
          </h3>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {startup.industry}
            {startup.hq_city ? ` · ${startup.hq_city}` : ""}
          </p>
        </div>
      </div>

      {startup.description ? (
        <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted-foreground">{startup.description}</p>
      ) : null}

      <div className="mt-4 flex items-center justify-between border-t border-border/70 pt-3">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Building2 className="size-3.5" />
          {startup.active_job_count > 0
            ? `${startup.active_job_count} open role${startup.active_job_count === 1 ? "" : "s"}`
            : "No open roles"}
        </span>
        {startup.active_job_count > 0 ? (
          <Badge variant="default">Hiring</Badge>
        ) : (
          <Badge variant="outline">Watching</Badge>
        )}
      </div>
    </Link>
  );
}
