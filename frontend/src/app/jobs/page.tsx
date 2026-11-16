import { Suspense } from "react";
import type { Metadata } from "next";

import { JobsExplorer } from "@/components/jobs-explorer";
import { JobCardSkeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Startup job openings in Ahmedabad & Gujarat",
  description:
    "Search verified startup jobs in Ahmedabad, Gandhinagar, GIFT City and across India. Filter by skill, experience, employment type, work arrangement and salary.",
  alternates: { canonical: "/jobs" },
};

export default function JobsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl space-y-3 px-4 py-10 sm:px-6">
          <JobCardSkeleton />
          <JobCardSkeleton />
          <JobCardSkeleton />
        </div>
      }
    >
      <JobsExplorer />
    </Suspense>
  );
}
