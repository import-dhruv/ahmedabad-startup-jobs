import Link from "next/link";
import { Briefcase } from "lucide-react";

const SECTIONS = [
  {
    title: "Discover",
    links: [
      { href: "/jobs", label: "All job openings" },
      { href: "/jobs?internship=true", label: "Internships" },
      { href: "/jobs?remote=true", label: "Remote roles" },
      { href: "/startups", label: "Startup directory" },
      { href: "/companies-hiring", label: "Companies hiring" },
    ],
  },
  {
    title: "Ecosystem",
    links: [
      { href: "/industries", label: "Industries" },
      { href: "/industries/artificial-intelligence", label: "AI startups" },
      { href: "/industries/fintech", label: "FinTech" },
      { href: "/industries/saas", label: "SaaS" },
      { href: "/industries/healthtech", label: "HealthTech" },
    ],
  },
  {
    title: "Platform",
    links: [
      { href: "/sources", label: "Data sources" },
      { href: "/methodology", label: "How it works" },
      { href: "/login", label: "Sign in" },
      { href: "/register", label: "Create account" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-24 border-t border-border bg-card/40">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <Link href="/" className="flex items-center gap-2.5">
              <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Briefcase className="size-4" />
              </span>
              <span className="text-sm font-semibold tracking-tight">AhmedabadJobs</span>
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted-foreground">
              Real-time startup hiring intelligence for Ahmedabad, Gandhinagar, GIFT City and the wider
              Gujarat ecosystem. Every listing links back to its original source.
            </p>
          </div>

          {SECTIONS.map((section) => (
            <div key={section.title}>
              <h3 className="text-sm font-semibold">{section.title}</h3>
              <ul className="mt-4 space-y-2.5">
                {section.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 flex flex-col gap-3 border-t border-border pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} Ahmedabad Startup Jobs. Listings belong to their respective employers.</p>
          <p>
            Data is aggregated from public job boards. Always confirm details on the employer&apos;s own
            listing before applying.
          </p>
        </div>
      </div>
    </footer>
  );
}
