import type { Metadata } from "next";

import { CandidateDashboard } from "@/components/candidate-dashboard";

export const metadata: Metadata = {
  title: "Your dashboard",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return <CandidateDashboard />;
}
