import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ExternalLink, Globe, Link2, MapPin, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobCard } from "@/components/job-card";
import { API_SERVER_URL, type StartupDetail } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export const revalidate = 300;

async function fetchStartup(slug: string): Promise<StartupDetail | null> {
  try {
    const res = await fetch(`${API_SERVER_URL}/startups/slug/${slug}`, {
      next: { revalidate: 300 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as StartupDetail;
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
  const startup = await fetchStartup(slug);
  if (!startup) return { title: "Startup not found" };
  const description =
    startup.description ??
    `${startup.name} is a ${startup.industry} startup${startup.hq_city ? ` headquartered in ${startup.hq_city}` : ""}. ${startup.active_job_count} open roles on Ahmedabad Startup Jobs.`;
  return {
    title: `${startup.name} — ${startup.industry} startup`,
    description,
    alternates: { canonical: `/startups/${startup.slug}` },
    openGraph: { title: startup.name, description, type: "profile" },
  };
}

export default async function StartupPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const startup = await fetchStartup(slug);
  if (!startup) notFound();

  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: startup.name,
    url: startup.website ?? undefined,
    logo: startup.logo_url ?? undefined,
    description: startup.description ?? undefined,
    sameAs: startup.linkedin_url ?? undefined,
    address: startup.hq_city
      ? {
          "@type": "PostalAddress",
          addressLocality: startup.hq_city,
          addressRegion: startup.hq_state ?? undefined,
          addressCountry: startup.hq_country ?? "India",
        }
      : undefined,
    numberOfEmployees: startup.size_range,
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }} />

      <Link
        href="/startups"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Startup directory
      </Link>

      <header className="mt-5 flex flex-col gap-5 border-b border-border pb-6 sm:flex-row sm:items-start">
        <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border bg-muted text-lg font-semibold text-muted-foreground">
          {startup.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={startup.logo_url} alt="" className="size-full object-contain p-1.5" />
          ) : (
            startup.name.slice(0, 2).toUpperCase()
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{startup.industry}</Badge>
            {startup.active_job_count > 0 ? (
              <Badge variant="default">{startup.active_job_count} open roles</Badge>
            ) : (
              <Badge variant="outline">No open roles right now</Badge>
            )}
            {startup.verification_status === "verified" ? (
              <Badge variant="success">Company verified</Badge>
            ) : null}
          </div>

          <h1 className="mt-2.5 text-2xl font-semibold tracking-tight sm:text-3xl">{startup.name}</h1>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
            {startup.hq_city ? (
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3.5" /> {startup.hq_city}
                {startup.hq_state ? `, ${startup.hq_state}` : ""}
              </span>
            ) : null}
            {startup.size_range ? (
              <span className="inline-flex items-center gap-1">
                <Users className="size-3.5" /> {startup.size_range} people
              </span>
            ) : null}
            {startup.founded_year ? <span>Founded {startup.founded_year}</span> : null}
            {startup.funding_stage ? <span>{startup.funding_stage}</span> : null}
          </div>

          {startup.description ? (
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {startup.description}
            </p>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            {startup.website ? (
              <Button asChild variant="outline" size="sm">
                <a href={startup.website} target="_blank" rel="noopener noreferrer nofollow">
                  <Globe className="size-4" /> Website <ExternalLink className="size-3" />
                </a>
              </Button>
            ) : null}
            {startup.linkedin_url ? (
              <Button asChild variant="outline" size="sm">
                <a href={startup.linkedin_url} target="_blank" rel="noopener noreferrer nofollow">
                  <Link2 className="size-4" /> LinkedIn
                </a>
              </Button>
            ) : null}
            {startup.careers_url ? (
              <Button asChild variant="outline" size="sm">
                <a href={startup.careers_url} target="_blank" rel="noopener noreferrer nofollow">
                  Careers page <ExternalLink className="size-3" />
                </a>
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_300px]">
        <section>
          <h2 className="text-lg font-semibold tracking-tight">
            Open roles{startup.recent_jobs.length ? ` (${startup.recent_jobs.length})` : ""}
          </h2>
          <div className="mt-4 space-y-3">
            {startup.recent_jobs.length ? (
              startup.recent_jobs.map((job) => <JobCard key={job.id} job={job} />)
            ) : (
              <Card className="p-10 text-center text-sm text-muted-foreground">
                No open roles are currently listed for {startup.name}. We keep checking their job board
                and will publish new openings as soon as they appear.
              </Card>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          {startup.founders.length ? (
            <Card>
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">Founders</h3>
                <ul className="mt-3 space-y-2.5">
                  {startup.founders.map((founder) => (
                    <li key={founder.id}>
                      <p className="text-sm font-medium">{founder.name}</p>
                      {founder.title ? (
                        <p className="text-xs text-muted-foreground">{founder.title}</p>
                      ) : null}
                      {founder.linkedin_url ? (
                        <a
                          href={founder.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer nofollow"
                          className="text-xs text-primary hover:underline"
                        >
                          LinkedIn profile
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          {startup.funding_rounds.length ? (
            <Card>
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">Funding</h3>
                <ul className="mt-3 space-y-3">
                  {startup.funding_rounds.map((round) => (
                    <li key={round.id} className="border-l-2 border-primary/40 pl-3">
                      <p className="text-sm font-medium">{round.round_type}</p>
                      {round.amount ? <p className="text-xs text-muted-foreground">{round.amount}</p> : null}
                      {round.announced_date ? (
                        <p className="text-xs text-muted-foreground">{formatDate(round.announced_date)}</p>
                      ) : null}
                      {round.investors.length ? (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {round.investors.join(", ")}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          {startup.tech_stack.length ? (
            <Card>
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">Technologies</h3>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {startup.tech_stack.map((tech) => (
                    <Badge key={tech} variant="secondary">
                      {tech}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardContent className="p-5">
              <h3 className="text-sm font-semibold">Data provenance</h3>
              <dl className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Discovered via</dt>
                  <dd className="text-right font-medium">{startup.hq_country ?? "—"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Verification</dt>
                  <dd className="text-right font-medium capitalize">{startup.verification_status}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Last checked</dt>
                  <dd className="text-right font-medium">{formatDate(startup.last_verified_at)}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
