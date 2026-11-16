import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Calendar,
  Clock,
  ExternalLink,
  MapPin,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { VerificationBadge } from "@/components/job-card";
import { SaveJobButton } from "@/components/save-job-button";
import { API_URL, type JobDetail } from "@/lib/api";
import { formatCurrency, formatDate, GEO_SCOPE_LABEL, timeAgo } from "@/lib/utils";

export const revalidate = 300;

async function fetchJob(slug: string): Promise<JobDetail | null> {
  try {
    const res = await fetch(`${API_URL}/jobs/slug/${slug}`, {
      next: { revalidate: 300 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as JobDetail;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const job = await fetchJob(slug);
  if (!job) return { title: "Job not found" };

  const company = job.company.name;
  const location = job.location.city ?? GEO_SCOPE_LABEL[job.geo_scope] ?? "India";
  const description =
    job.ai_summary ??
    `${job.title} at ${company} — ${location}. ${job.employment_type ?? "Open position"}${
      job.experience_level ? `, ${job.experience_level} experience` : ""
    }. Apply on the employer's own listing.`;

  return {
    title: `${job.title} at ${company}`,
    description,
    alternates: { canonical: `/jobs/${job.slug}` },
    openGraph: {
      type: "article",
      title: `${job.title} at ${company}`,
      description,
      url: `/jobs/${job.slug}`,
    },
    twitter: { card: "summary", title: `${job.title} at ${company}`, description },
  };
}

function jobPostingSchema(job: JobDetail) {
  const location = {
    "@type": "Place",
    address: {
      "@type": "PostalAddress",
      addressLocality: job.location.city ?? undefined,
      addressRegion: job.location.state ?? undefined,
      addressCountry: job.location.country ?? "IN",
    },
  };

  const employmentTypeMap: Record<string, string> = {
    "Full-time": "FULL_TIME",
    "Part-time": "PART_TIME",
    Internship: "INTERN",
    Contract: "CONTRACTOR",
    Freelance: "CONTRACTOR",
    Apprenticeship: "APPRENTICESHIP",
  };

  const remote = job.work_arrangement === "Remote" || job.is_remote;

  return {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description:
      job.ai_summary ??
      (job.description ? job.description.slice(0, 9000) : `${job.title} at ${job.company.name}`),
    datePosted: job.posted_at ?? job.discovered_at ?? new Date().toISOString(),
    validThrough: job.deadline ?? undefined,
    employmentType: job.employment_type
      ? employmentTypeMap[job.employment_type] ?? "FULL_TIME"
      : undefined,
    hiringOrganization: {
      "@type": "Organization",
      name: job.company.name,
      sameAs: job.startup?.website ?? undefined,
      logo: job.company.logo_url ?? undefined,
    },
    jobLocation: remote
      ? { "@type": "Place", address: { "@type": "PostalAddress", addressCountry: job.location.country ?? "IN" } }
      : location,
    applicantLocationRequirements: {
      "@type": "Country",
      name: job.location.country ?? "India",
    },
    jobLocationType: job.work_arrangement === "Remote" ? "TELECOMMUTE" : undefined,
    directApply: true,
    url: job.original_url || job.apply_url,
    baseSalary: job.salary.disclosed && job.salary.min
      ? {
          "@type": "MonetaryAmount",
          currency: job.salary.currency ?? "INR",
          value: {
            "@type": "QuantitativeValue",
            minValue: job.salary.min ?? 0,
            maxValue: job.salary.max ?? job.salary.min ?? 0,
            unitText: job.salary.period === "month" ? "MONTH" : "YEAR",
          },
        }
      : undefined,
  };
}

export default async function JobDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const job = await fetchJob(slug);
  if (!job) notFound();

  const salary = formatCurrency(job.salary.max ?? job.salary.min, job.salary.currency, job.salary.period);
  const locationLabel = [job.location.city, job.location.state].filter(Boolean).join(", ") || job.location.raw;

  const schema = jobPostingSchema(job);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <Link
        href="/jobs"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> All openings
      </Link>

      <div className="mt-5 flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <VerificationBadge status={job.verification_status} />
            {job.employment_type ? <Badge variant="secondary">{job.employment_type}</Badge> : null}
            {job.work_arrangement ? <Badge variant="secondary">{job.work_arrangement}</Badge> : null}
            {job.experience_level ? <Badge variant="outline">{job.experience_level}</Badge> : null}
            {job.categories?.includes("Internship") ? <Badge variant="accent">Internship</Badge> : null}
          </div>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">{job.title}</h1>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {job.company.slug ? (
              <Link href={`/startups/${job.company.slug}`} className="font-medium text-foreground hover:text-primary">
                {job.company.name}
              </Link>
            ) : (
              <span className="font-medium text-foreground">{job.company.name}</span>
            )}
            {job.company.industry ? (
              <>
                <span aria-hidden>·</span>
                <span>{job.company.industry}</span>
              </>
            ) : null}
            {locationLabel ? (
              <>
                <span aria-hidden>·</span>
                <span className="inline-flex items-center gap-1">
                  <MapPin className="size-3.5" /> {locationLabel}
                </span>
              </>
            ) : null}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3.5" /> Posted {timeAgo(job.posted_at ?? job.discovered_at)}
            </span>
            <span className="inline-flex items-center gap-1">
              <ShieldCheck className="size-3.5" /> Verified {timeAgo(job.last_verified_at)}
            </span>
            {job.source ? <span>Source: {job.source.name}</span> : null}
          </div>
        </div>

        <Card className="w-full shrink-0 lg:w-72">
          <CardContent className="p-5">
            {salary ? (
              <div className="mb-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Compensation</p>
                <p className="mt-1 text-lg font-semibold text-success">{salary}</p>
              </div>
            ) : (
              <div className="mb-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Compensation</p>
                <p className="mt-1 text-sm text-muted-foreground">Not disclosed by the employer</p>
              </div>
            )}

            <Button asChild size="lg" className="w-full">
              <a href={job.apply_url} target="_blank" rel="noopener noreferrer nofollow">
                Apply on {job.company.name} <ExternalLink className="size-4" />
              </a>
            </Button>

            <SaveJobButton jobId={job.id} className="mt-2 w-full" />

            <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
              You will be redirected to the employer&apos;s original listing. This platform never handles
              applications on your behalf.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_280px]">
        <div className="space-y-6">
          {job.ai_summary ? (
            <Card className="border-primary/25 bg-primary/[0.04]">
              <CardContent className="p-5">
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <Sparkles className="size-4 text-primary" /> Role summary
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{job.ai_summary}</p>
                <p className="mt-2 text-[11px] text-muted-foreground/80">
                  Generated summary of the original listing — check the source for full details.
                </p>
              </CardContent>
            </Card>
          ) : null}

          {job.description ? (
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold tracking-tight">About this role</h2>
                <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">
                  {job.description.split(/\n{2,}/).map((paragraph, index) => (
                    <p key={index}>{paragraph}</p>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          {job.responsibilities.length ? (
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold tracking-tight">Responsibilities</h2>
                <ul className="mt-3 space-y-2 text-sm leading-relaxed text-muted-foreground">
                  {job.responsibilities.map((item, index) => (
                    <li key={index} className="flex gap-2.5">
                      <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-primary/60" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          {job.qualifications.length ? (
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold tracking-tight">Requirements</h2>
                <ul className="mt-3 space-y-2 text-sm leading-relaxed text-muted-foreground">
                  {job.qualifications.map((item, index) => (
                    <li key={index} className="flex gap-2.5">
                      <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-primary/60" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <aside className="space-y-4">
          <Card>
            <CardContent className="p-5">
              <h3 className="text-sm font-semibold">At a glance</h3>
              <dl className="mt-3 space-y-2.5 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Location</dt>
                  <dd className="text-right font-medium">{locationLabel || "Flexible"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Scope</dt>
                  <dd className="text-right font-medium">{GEO_SCOPE_LABEL[job.geo_scope] ?? job.geo_scope}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="text-right font-medium">{job.employment_type ?? "Not specified"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Arrangement</dt>
                  <dd className="text-right font-medium">{job.work_arrangement ?? "Not specified"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Experience</dt>
                  <dd className="text-right font-medium">{job.experience_level ?? "Not specified"}</dd>
                </div>
                {job.deadline ? (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Apply by</dt>
                    <dd className="text-right font-medium">{formatDate(job.deadline)}</dd>
                  </div>
                ) : null}
              </dl>
            </CardContent>
          </Card>

          {job.skills.length ? (
            <Card>
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">Skills</h3>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {job.skills.map((skill) => (
                    <Badge key={skill} variant="secondary">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          {job.startup ? (
            <Card>
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">About {job.startup.name}</h3>
                {job.startup.description ? (
                  <p className="mt-2 line-clamp-4 text-sm text-muted-foreground">{job.startup.description}</p>
                ) : null}
                <dl className="mt-3 space-y-2 text-sm">
                  {job.startup.industry ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted-foreground">Industry</dt>
                      <dd className="text-right font-medium">{job.startup.industry}</dd>
                    </div>
                  ) : null}
                  {job.startup.hq_city ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted-foreground">HQ</dt>
                      <dd className="text-right font-medium">{job.startup.hq_city}</dd>
                    </div>
                  ) : null}
                  {job.startup.size_range ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted-foreground">Team size</dt>
                      <dd className="text-right font-medium">{job.startup.size_range}</dd>
                    </div>
                  ) : null}
                </dl>
                {job.startup.slug ? (
                  <Button asChild variant="outline" size="sm" className="mt-4 w-full">
                    <Link href={`/startups/${job.startup.slug}`}>
                      <Building2 className="size-4" /> Company profile
                    </Link>
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {job.references.length > 1 ? (
            <Card>
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">Also listed on</h3>
                <ul className="mt-3 space-y-2">
                  {job.references.map((reference) => (
                    <li key={reference.id}>
                      <a
                        href={reference.source_url}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                      >
                        <Calendar className="size-3.5" /> Source listing
                        <ExternalLink className="size-3" />
                      </a>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
