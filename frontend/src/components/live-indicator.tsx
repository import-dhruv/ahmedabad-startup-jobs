"use client";

import * as React from "react";
import { Radio } from "lucide-react";

import { API_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LiveEvent {
  event: string;
  data: Record<string, unknown> & { ts?: string };
}

/**
 * Subscribes to the ingestion event stream and surfaces new-activity signals.
 * The counter is derived from real ingestion events pushed by the API.
 */
export function LiveIndicator({ className }: { className?: string }) {
  const [connected, setConnected] = React.useState(false);
  const [lastEvent, setLastEvent] = React.useState<LiveEvent | null>(null);
  const [count, setCount] = React.useState(0);

  React.useEffect(() => {
    let source: EventSource | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      source = new EventSource(`${API_URL}/events`);
      source.onopen = () => setConnected(true);
      source.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data) as LiveEvent;
          setLastEvent(parsed);
          if (parsed.event === "jobs.discovered") {
            setCount((current) => current + Number(parsed.data?.created ?? 0));
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      source.onerror = () => {
        setConnected(false);
        source?.close();
        if (!closed) setTimeout(connect, 8000);
      };
    };

    connect();
    return () => {
      closed = true;
      source?.close();
    };
  }, []);

  return (
    <span className={cn("inline-flex items-center gap-2 text-xs text-muted-foreground", className)}>
      <span className="relative flex size-2">
        <span
          className={cn(
            "absolute inline-flex size-full rounded-full opacity-70",
            connected ? "live-dot bg-success" : "bg-muted-foreground",
          )}
        />
      </span>
      {connected ? (
        <span>
          Live
          {count > 0 ? ` · ${count} new` : ""}
          {lastEvent?.event === "jobs.discovered"
            ? ` · ${String(lastEvent.data?.source ?? "source")} just synced`
            : ""}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1">
          <Radio className="size-3" /> Connecting…
        </span>
      )}
    </span>
  );
}
