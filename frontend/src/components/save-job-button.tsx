"use client";

import * as React from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";
import { userApi } from "@/lib/api";

export function SaveJobButton({ jobId, className }: { jobId: string; className?: string }) {
  const { user, token } = useAuth();
  const [saved, setSaved] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!token) return;
    userApi
      .savedJobs(token)
      .then((data) => setSaved(data.items.some((job) => job.id === jobId)))
      .catch(() => undefined);
  }, [token, jobId]);

  const toggle = async () => {
    if (!user || !token) {
      toast.error("Sign in to save jobs");
      return;
    }
    setBusy(true);
    try {
      if (saved) {
        await userApi.unsaveJob(token, jobId);
        setSaved(false);
        toast.success("Removed from saved jobs");
      } else {
        await userApi.saveJob(token, jobId);
        setSaved(true);
        toast.success("Saved to your list");
      }
    } catch {
      toast.error("Could not update saved jobs");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button variant="outline" className={className} onClick={toggle} disabled={busy}>
      {saved ? <BookmarkCheck className="size-4" /> : <Bookmark className="size-4" />}
      {saved ? "Saved" : "Save job"}
    </Button>
  );
}
