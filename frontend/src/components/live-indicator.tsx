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
 *
 * This uses fetch instead of EventSource because the tunnel needs an extra
 * request header to avoid ngrok's browser interstitial, and EventSource
 * cannot set custom headers.
 */
export function LiveIndicator({ className }: { className?: string }) {
  const [connected, setConnected] = React.useState(false);
  const [lastEvent, setLastEvent] = React.useState<LiveEvent | null>(null);
  const [count, setCount] = React.useState(0);

  React.useEffect(() => {
    let controller: AbortController | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = async () => {
      if (closed) return;
      controller = new AbortController();
      try {
        const response = await fetch(`${API_URL}/events`, {
          headers: {
            Accept: "text/event-stream",
            "ngrok-skip-browser-warning": "true",
          },
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok || !response.body) throw new Error("stream unavailable");
        setConnected(true);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!closed) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            const data = frame
              .split("\n")
              .find((line) => line.startsWith("data:"))
              ?.slice(5)
              .trim();
            if (!data) continue;
            try {
              const parsed = JSON.parse(data) as LiveEvent;
              setLastEvent(parsed);
              if (parsed.event === "jobs.discovered") {
                setCount((current) => current + Number(parsed.data?.created ?? 0));
              }
            } catch {
              /* ignore malformed frames */
            }
          }
        }
      } catch {
        /* reconnect below */
      } finally {
        setConnected(false);
        if (!closed) retry = setTimeout(() => void connect(), 8000);
      }
    };

    void connect();
    return () => {
      closed = true;
      controller?.abort();
      if (retry) clearTimeout(retry);
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
