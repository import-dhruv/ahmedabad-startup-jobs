import type { Metadata } from "next";
import { CheckCircle2, Database, Fingerprint, Radar, ShieldCheck, Sparkles } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How Ahmedabad Startup Jobs discovers, verifies and publishes startup job openings — the ingestion pipeline, deduplication rules and data-quality guarantees.",
  alternates: { canonical: "/methodology" },
};

const STAGES = [
  {
    icon: Radar,
    title: "1. Discovery",
    body: "We look for company websites, then probe the public job-board endpoints that companies embed on their careers pages — Greenhouse, Lever, Ashby, Workable and schema.org job markup. Every board is confirmed to exist by fetching it live.",
  },
  {
    icon: Database,
    title: "2. Ingestion",
    body: "A polite HTTP client honours robots.txt, rate-limits per host, and retries with exponential backoff. Payloads are normalised into one schema regardless of which platform they came from.",
  },
  {
    icon: Fingerprint,
    title: "3. Deduplication",
    body: "Two postings are merged only when there is corroborating evidence: an identical application URL, the same company with a matching normalised title and location, or a near-identical description. A matching title alone is never enough.",
  },
  {
    icon: ShieldCheck,
    title: "4. Verification",
    body: "Application links are re-checked on a daily schedule. Listings stop being presented as active once the link stops resolving; they move to stale, then expired. Each listing shows its source and last verification time.",
  },
  {
    icon: Sparkles,
    title: "5. Enrichment",
    body: "Skills, categories, seniority and salary are extracted from the employer's own words. If an AI provider is configured it can refine classification and write a short summary — always labelled as generated, never presented as measured data.",
  },
  {
    icon: CheckCircle2,
    title: "6. Publication",
    body: "Only listings we have actually read from a public source are published, and every one of them links back to the original posting. We never invent companies, roles or salary ranges.",
  },
];

const GUARANTEES = [
  "Every listing stores the exact URL it was read from.",
  "Every listing records when it was discovered and when it was last verified.",
  "Company headquarters is stored separately from the job's location.",
  "AI-generated content is labelled and kept apart from measured statistics.",
  "Duplicates across sources are merged while retaining every source reference.",
  "Sources that disallow automated access are not crawled.",
];

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">How this platform works</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Startup job boards are fragmented: a company might publish on its own careers page, on an ATS
          it embeds, and on two aggregators at once. This platform reads all of those public places,
          normalises what it finds, removes duplicates, verifies what is still live, and publishes the
          result with full source attribution.
        </p>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {STAGES.map((stage) => (
          <Card key={stage.title}>
            <CardContent className="p-5">
              <stage.icon className="size-5 text-primary" />
              <h2 className="mt-3 text-sm font-semibold tracking-tight">{stage.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{stage.body}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-6">
        <CardContent className="p-6">
          <h2 className="text-lg font-semibold tracking-tight">Our data-quality guarantees</h2>
          <ul className="mt-4 space-y-2.5">
            {GUARANTEES.map((guarantee) => (
              <li key={guarantee} className="flex gap-2.5 text-sm text-muted-foreground">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                {guarantee}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardContent className="p-6">
          <h2 className="text-lg font-semibold tracking-tight">What &quot;verified&quot; means</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            A listing is marked <strong>verified</strong> only after its application URL has resolved
            successfully during a recent run and the employer&apos;s page still lists the role. Listings we
            have just imported are marked <strong>unverified</strong> until that first check completes.
            Listings we can no longer confirm become <strong>stale</strong>, and once they have been
            absent for a prolonged period they are marked <strong>expired</strong> and removed from the
            public board.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
