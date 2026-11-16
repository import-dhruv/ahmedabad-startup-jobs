import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { IndustryLanding } from "@/components/industry-landing";
import { API_URL } from "@/lib/api";

export const revalidate = 300;

async function fetchIndustry(slug: string) {
  try {
    const res = await fetch(`${API_URL}/jobs?industry=${encodeURIComponent(slug)}&per_page=25`, {
      next: { revalidate: 300 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as { total: number; items: unknown[] };
  } catch {
    return null;
  }
}

function titleFromSlug(slug: string) {
  return slug
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const title = titleFromSlug(slug);
  return {
    title: `${title} startup jobs in Ahmedabad`,
    description: `Open roles at ${title} startups in Ahmedabad, Gandhinagar, GIFT City and across Gujarat — with direct application links and source attribution.`,
    alternates: { canonical: `/industries/${slug}` },
  };
}

export default async function IndustryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const title = titleFromSlug(slug);
  const data = await fetchIndustry(title);
  if (!data) notFound();

  return <IndustryLanding slug={slug} title={title} total={data.total} />;
}
