import { Suspense } from "react";
import type { Metadata } from "next";

import { CompaniesHiring } from "@/components/companies-hiring";
import { JobCardSkeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Companies hiring now",
  description:
    "Startups across Ahmedabad and Gujarat that are actively hiring right now, ranked by number of open roles.",
  alternates: { canonical: "/companies-hiring" },
};

export default function CompaniesHiringPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl space-y-3 px-4 py-10 sm:px-6">
          <JobCardSkeleton />
          <JobCardSkeleton />
        </div>
      }
    >
      <CompaniesHiring />
    </Suspense>
  );
}
