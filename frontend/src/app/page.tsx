import Link from "next/link";
import {
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  Flame,
  GraduationCap,
  MapPin,
  Radio,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobCard, StartupCard } from "@/components/job-card";
import { LiveIndicator } from "@/components/live-indicator";
import { SearchHero } from "@/components/search-hero";
import { TrendChart } from "@/components/trend-chart";
import { SkillCloud } from "@/components/skill-cloud";
import { jobsApi, statsApi, startupsApi } from "@/lib/api";
import { formatCompactNumber } from "@/lib/utils";

export const revalidate = 120;

async function safe<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch {
    return null;
  }
}

export default async function HomePage() {
  const [stats, recentJobs, recentStartups, trends, skills, hiring, internships, topCompanies] =
    await Promise.all([
      safe(statsApi.dashboard()),
      safe(statsApi.recentJobs(10)),
      safe(startupsApi.list({ limit: 8, sort: "recent" })),
      safe(statsApi.trends(30)),
      safe(statsApi.skills()),
      safe(statsApi.industries()),
      safe(jobsApi.search({ internship: true, per_page: 6, scope: ["ahmedabad", "gujarat", "india_remote", "india"] })),
      safe(statsApi.hiring()),
    ]);

  const statCards = [
    {
      label: "Active openings",
      value: stats?.total_active_jobs ?? 0,
      hint: `${stats?.ahmedabad_jobs ?? 0} in Ahmedabad`,
      icon: BriefcaseBusiness,
    },
    {
      label: "Startups tracked",
      value: stats?.total_startups ?? 0,
      hint: `${stats?.companies_hiring ?? 0} actively hiring`,
      icon: Building2,
    },
    {
      label: "New in 24h",
      value: stats?.new_jobs_24h ?? 0,
      hint: `${stats?.new_jobs_7d ?? 0} in the last 7 days`,
      icon: Sparkles,
    },
    {
      label: "Internships",
      value: stats?.internship_openings ?? 0,
      hint: "Open to students & freshers",
      icon: GraduationCap,
    },
  ];

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[520px] grid-bg opacity-60" />
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] bg-gradient-to-b from-primary/8 via-transparent to-transparent" />

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-4 pb-12 pt-14 sm:px-6 sm:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <Badge variant="accent" className="mb-6 gap-1.5 px-3 py-1">
            <Radio className="size-3" />
            Live · {formatCompactNumber(stats?.new_jobs_24h ?? 0)} openings discovered in the last 24h
          </Badge>

          <h1 className="text-balance text-4xl font-semibold leading-[1.08] tracking-tight sm:text-5xl md:text-6xl">
            <span className="text-gradient">Every Ahmedabad startup.</span>
            <br />
            Every hiring opportunity. One platform.
          </h1>

          <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            We continuously crawl public job boards and startup career pages across Ahmedabad,
            Gandhinagar, GIFT City and Sanand — then verify every link before you see it.
          </p>

          <SearchHero />

          <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="text-muted-foreground">Popular:</span>
            {[
              "AI Engineer",
              "Python Developer",
              "Machine Learning Intern",
              "Backend Engineer",
              "Flutter Intern",
              "Data Scientist",
            ].map((term) => (
              <Link
                key={term}
                href={`/jobs?q=${encodeURIComponent(term)}`}
                className="rounded-full border border-border bg-card px-2.5 py-1 text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {term}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          {statCards.map((card) => (
            <Card key={card.label} className="overflow-hidden">
              <CardContent className="p-4 sm:p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {card.label}
                  </span>
                  <card.icon className="size-4 text-muted-foreground/70" />
                </div>
                <p className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                  {formatCompactNumber(card.value)}
                </p>
                <p className="mt-1 truncate text-xs text-muted-foreground">{card.hint}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Recent jobs */}
      <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight sm:text-2xl">
              <Flame className="size-5 text-orange-500" />
              Latest opportunities
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Freshly discovered and verified against their original source.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/jobs">
              View all jobs <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>

        <div className="mt-6 grid gap-3">
          {recentJobs?.items?.length ? (
            recentJobs.items.map((job) => <JobCard key={job.id} job={job} />)
          ) : (
            <Card className="p-10 text-center text-sm text-muted-foreground">
              No jobs have been discovered yet. Start the ingestion pipeline to populate the board.
            </Card>
          )}
        </div>
      </section>

      {/* Startups */}
      <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight sm:text-2xl">
              <Building2 className="size-5 text-primary" />
              Recently discovered startups
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Companies found by the discovery engine, with their careers page on record.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/startups">
              Browse directory <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {recentStartups?.length ? (
            recentStartups.map((startup) => (
              <StartupCard
                key={startup.id}
                startup={{ ...startup, active_job_count: startup.active_job_count ?? 0 }}
              />
            ))
          ) : (
            <Card className="p-8 text-center text-sm text-muted-foreground sm:col-span-2 lg:col-span-4">
              The startup directory populates as discovery runs.
            </Card>
          )}
        </div>
      </section>

      {/* Trending skills */}
      {skills?.skills?.length ? (
        <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
          <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight sm:text-2xl">
            <TrendingUp className="size-5 text-primary" />
            Trending technologies
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Skills ranked by openings in the last 60 days, with change vs. the previous period.
          </p>
          <div className="mt-6">
            <SkillCloud skills={skills.skills.slice(0, 18)} />
          </div>
        </section>
      ) : null}

      {/* Internships */}
      {internships?.items?.length ? (
        <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight sm:text-2xl">
                <GraduationCap className="size-5 text-primary" />
                Latest internships
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Entry points for students, freshers and career switchers.
              </p>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link href="/jobs?internship=true">
                All internships <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
          <div className="mt-6 grid gap-3 lg:grid-cols-2">
            {internships.items.slice(0, 4).map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        </section>
      ) : null}

      {/* Hiring insights */}
      <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <Card>
            <CardContent className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight">Hiring activity</h2>
                  <p className="text-sm text-muted-foreground">Openings published per day, last 30 days</p>
                </div>
                <LiveIndicator />
              </div>
              <div className="mt-4">
                <TrendChart data={trends?.series ?? []} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <h2 className="text-lg font-semibold tracking-tight">Companies hiring now</h2>
              <p className="text-sm text-muted-foreground">Ranked by number of open roles</p>
              <ul className="mt-4 space-y-2.5">
                {topCompanies?.companies?.length ? (
                  topCompanies.companies.slice(0, 7).map((company) => (
                    <li key={company.startup_id ?? company.name}>
                      <Link
                        href={company.slug ? `/startups/${company.slug}` : "/startups"}
                        className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-accent"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate text-sm font-medium">{company.name}</span>
                          {company.industry ? (
                            <span className="hidden truncate text-xs text-muted-foreground sm:inline">
                              {company.industry}
                            </span>
                          ) : null}
                        </span>
                        <Badge variant="secondary">{company.openings}</Badge>
                      </Link>
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-muted-foreground">No company data yet.</li>
                )}
              </ul>
              <Button asChild variant="ghost" size="sm" className="mt-4 w-full">
                <Link href="/companies-hiring">
                  See all companies <ArrowRight className="size-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Industries */}
      {hiring?.industries?.length ? (
        <section className="mx-auto mt-16 max-w-7xl px-4 sm:px-6">
          <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Hiring by industry</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Measured from active openings linked to companies in our directory.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {hiring.industries.map((industry) => (
              <Link
                key={industry.industry}
                href={`/industries/${industry.industry.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                className="group flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm transition-colors hover:border-primary/40"
              >
                <span className="font-medium">{industry.industry}</span>
                <span className="text-xs text-muted-foreground">{industry.count}</span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {/* CTA */}
      <section className="mx-auto mt-20 max-w-7xl px-4 sm:px-6">
        <Card className="overflow-hidden border-primary/25 bg-gradient-to-br from-primary/[0.07] via-card to-card">
          <CardContent className="flex flex-col items-start gap-6 p-8 sm:p-10 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-xl">
              <h2 className="text-2xl font-semibold tracking-tight">
                Get alerted when the right role opens up
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                Create a profile with your skills and experience, then let the platform watch every
                startup board in the ecosystem and tell you the moment something matches.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link href="/register">Create your profile</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/jobs">
                  <MapPin className="size-4" /> Explore openings
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
