import type { Metadata } from "next";

import { StartupsExplorer } from "@/components/startups-explorer";

export const metadata: Metadata = {
  title: "Startup directory",
  description:
    "Browse verified startups across Ahmedabad, Gandhinagar, GIFT City and Gujarat — with headquarters, industry, funding stage, team size and live openings.",
  alternates: { canonical: "/startups" },
};

export default function StartupsPage() {
  return <StartupsExplorer />;
}
