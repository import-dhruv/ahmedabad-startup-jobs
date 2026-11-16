"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  PlayCircle,
  ShieldAlert,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/components/auth-provider";
import { api } from "@/lib/api";
import { formatDate, timeAgo } from "@/lib/utils";

interface Overview {
  total_sources: number;
  active_connectors: number;
  jobs_discovered_today: number;
  successful_runs_24h: number;
  failed_runs_24h: number;
  duplicates_detected_24h: number;
  jobs_awaiting_verification: number;
  total_startups: number;
  total_jobs: number;
  active_jobs: number;
  expired_jobs: number;
  rejected_jobs: number;
  database_size_mb: number | null;
}

interface Run {
  id: string;
  source_id: string | null;
  connector: string;
  status: string;
  trigger: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  jobs_found: number;
  jobs_created: number;
  jobs_updated: number;
  duplicates_found: number;
  errors_count: number;
  message: string | null;
}

interface Health {
  id: string;
  source_id: string;
  status: string;
  consecutive_failures: number;
  total_runs: number;
  total_failures: number;
  success_rate: number;
  avg_duration_ms: number;
  last_success_at: string | null;
  last_error: string | null;
  jobs_last_run: number;
}

interface SourceRow {
  id: string;
  name: string;
  slug: string;
  connector_type: string;
  is_active: boolean;
  total_jobs_discovered: number;
  last_run_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
}

interface ErrorRow {
  id: string;
  error_type: string | null;
  message: string;
  url: string | null;
  created_at: string;
}

export function AdminDashboard() {
  const router = useRouter();
  const { user, token, loading } = useAuth();

  React.useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) router.replace("/login?next=/admin");
  }, [loading, user, router]);

  const overview = useQuery({
    queryKey: ["admin-overview", token],
    queryFn: () => api.get<Overview>("/admin/overview", token),
    enabled: Boolean(token) && user?.role === "admin",
    refetchInterval: 15000,
  });

  const runs = useQuery({
    queryKey: ["admin-runs", token],
    queryFn: () => api.get<Run[]>("/admin/runs?limit=40", token),
    enabled: Boolean(token) && user?.role === "admin",
    refetchInterval: 20000,
  });

  const health = useQuery({
    queryKey: ["admin-health", token],
    queryFn: () => api.get<Health[]>("/admin/health", token),
    enabled: Boolean(token) && user?.role === "admin",
  });

  const sources = useQuery({
    queryKey: ["admin-sources", token],
    queryFn: () => api.get<SourceRow[]>("/admin/sources", token),
    enabled: Boolean(token) && user?.role === "admin",
  });

  const errors = useQuery({
    queryKey: ["admin-errors", token],
    queryFn: () => api.get<ErrorRow[]>("/admin/errors?limit=30", token),
    enabled: Boolean(token) && user?.role === "admin",
  });

  const runSource = async (sourceId: string) => {
    if (!token) return;
    try {
      await api.post(`/admin/sources/${sourceId}/run`, undefined, token);
      toast.success("Ingestion queued for this source");
      setTimeout(() => runs.refetch(), 3000);
    } catch {
      toast.error("Could not queue the ingestion run");
    }
  };

  if (loading || !user) {
    return <div className="p-16 text-center text-sm text-muted-foreground">Loading…</div>;
  }

  if (user.role !== "admin") {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <ShieldAlert className="mx-auto size-8 text-destructive" />
        <h1 className="mt-4 text-lg font-semibold">Administrator access required</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Sign in with an administrator account to manage data sources and verify listings.
        </p>
      </div>
    );
  }

  const cards = [
    {
      label: "Sources connected",
      value: overview.data?.total_sources ?? 0,
      hint: `${overview.data?.active_connectors ?? 0} active connectors`,
      icon: Database,
    },
    {
      label: "Discovered today",
      value: overview.data?.jobs_discovered_today ?? 0,
      hint: `${overview.data?.duplicates_detected_24h ?? 0} duplicates caught`,
      icon: Activity,
    },
    {
      label: "Runs (24h)",
      value: (overview.data?.successful_runs_24h ?? 0) + (overview.data?.failed_runs_24h ?? 0),
      hint: `${overview.data?.failed_runs_24h ?? 0} failed`,
      icon: CheckCircle2,
    },
    {
      label: "Awaiting verification",
      value: overview.data?.jobs_awaiting_verification ?? 0,
      hint: `${overview.data?.expired_jobs ?? 0} expired`,
      icon: AlertTriangle,
    },
    {
      label: "Startups tracked",
      value: overview.data?.total_startups ?? 0,
      hint: "in the directory",
      icon: Users,
    },
    {
      label: "Active openings",
      value: overview.data?.active_jobs ?? 0,
      hint: `${overview.data?.total_jobs ?? 0} total records`,
      icon: CheckCircle2,
    },
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Admin console</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ingestion monitoring, source health and data-quality controls.
        </p>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {card.label}
                </span>
                <card.icon className="size-4 text-muted-foreground/70" />
              </div>
              <p className="mt-2 text-2xl font-semibold tracking-tight">{card.value}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{card.hint}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="sources" className="mt-8">
        <TabsList>
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="health">Health</TabsTrigger>
          <TabsTrigger value="errors">Errors</TabsTrigger>
        </TabsList>

        <TabsContent value="sources">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-5 py-3 font-medium">Source</th>
                      <th className="px-5 py-3 font-medium">Connector</th>
                      <th className="px-5 py-3 font-medium">Jobs found</th>
                      <th className="px-5 py-3 font-medium">Last success</th>
                      <th className="px-5 py-3 font-medium">State</th>
                      <th className="px-5 py-3" />
                    </tr>
                  </thead>
                  <tbody>
                    {sources.data?.map((source) => (
                      <tr key={source.id} className="border-b border-border/60 last:border-0">
                        <td className="px-5 py-3 font-medium">{source.name}</td>
                        <td className="px-5 py-3">
                          <Badge variant="secondary">{source.connector_type}</Badge>
                        </td>
                        <td className="px-5 py-3">{source.total_jobs_discovered}</td>
                        <td className="px-5 py-3 text-muted-foreground">
                          {source.last_success_at ? timeAgo(source.last_success_at) : "—"}
                        </td>
                        <td className="px-5 py-3">
                          <Badge variant={source.is_active ? "success" : "outline"}>
                            {source.is_active ? "Active" : "Disabled"}
                          </Badge>
                        </td>
                        <td className="px-5 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => runSource(source.id)}
                            aria-label="Run now"
                          >
                            <PlayCircle className="size-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="runs">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-5 py-3 font-medium">Connector</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium">Found</th>
                      <th className="px-5 py-3 font-medium">New</th>
                      <th className="px-5 py-3 font-medium">Updated</th>
                      <th className="px-5 py-3 font-medium">Duplicates</th>
                      <th className="px-5 py-3 font-medium">Duration</th>
                      <th className="px-5 py-3 font-medium">Finished</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.data?.map((run) => (
                      <tr key={run.id} className="border-b border-border/60 last:border-0">
                        <td className="px-5 py-3 font-medium">{run.connector}</td>
                        <td className="px-5 py-3">
                          <Badge
                            variant={
                              run.status === "success"
                                ? "success"
                                : run.status === "failed"
                                  ? "destructive"
                                  : run.status === "partial"
                                    ? "warning"
                                    : "outline"
                            }
                          >
                            {run.status}
                          </Badge>
                        </td>
                        <td className="px-5 py-3">{run.jobs_found}</td>
                        <td className="px-5 py-3">{run.jobs_created}</td>
                        <td className="px-5 py-3">{run.jobs_updated}</td>
                        <td className="px-5 py-3">{run.duplicates_found}</td>
                        <td className="px-5 py-3 text-muted-foreground">
                          {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : "—"}
                        </td>
                        <td className="px-5 py-3 text-muted-foreground">
                          {run.finished_at ? timeAgo(run.finished_at) : "—"}
                        </td>
                      </tr>
                    ))}
                    {!runs.data?.length ? (
                      <tr>
                        <td colSpan={8} className="px-5 py-10 text-center text-muted-foreground">
                          No ingestion runs recorded yet.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="health">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {health.data?.map((row) => (
              <Card key={row.id}>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Source health</span>
                    <Badge
                      variant={
                        row.status === "healthy"
                          ? "success"
                          : row.status === "degraded"
                            ? "warning"
                            : "destructive"
                      }
                    >
                      {row.status}
                    </Badge>
                  </div>
                  <p className="mt-3 text-2xl font-semibold tracking-tight">
                    {(row.success_rate * 100).toFixed(0)}%
                  </p>
                  <p className="text-xs text-muted-foreground">success rate over {row.total_runs} runs</p>
                  <dl className="mt-3 space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Avg duration</dt>
                      <dd>{(row.avg_duration_ms / 1000).toFixed(1)}s</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Consecutive failures</dt>
                      <dd>{row.consecutive_failures}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Jobs last run</dt>
                      <dd>{row.jobs_last_run}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Last success</dt>
                      <dd>{row.last_success_at ? timeAgo(row.last_success_at) : "—"}</dd>
                    </div>
                  </dl>
                  {row.last_error ? (
                    <p className="mt-3 rounded bg-destructive/10 p-2 text-[11px] text-destructive">
                      {row.last_error}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            ))}
            {!health.data?.length ? (
              <Card className="p-10 text-center text-sm text-muted-foreground sm:col-span-2 lg:col-span-3">
                No source health snapshots yet.
              </Card>
            ) : null}
          </div>
        </TabsContent>

        <TabsContent value="errors">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-5 py-3 font-medium">Type</th>
                      <th className="px-5 py-3 font-medium">Message</th>
                      <th className="px-5 py-3 font-medium">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {errors.data?.map((error) => (
                      <tr key={error.id} className="border-b border-border/60 last:border-0">
                        <td className="px-5 py-3 font-medium">{error.error_type ?? "error"}</td>
                        <td className="max-w-xl px-5 py-3 text-muted-foreground">{error.message}</td>
                        <td className="px-5 py-3 text-muted-foreground">{formatDate(error.created_at)}</td>
                      </tr>
                    ))}
                    {!errors.data?.length ? (
                      <tr>
                        <td colSpan={3} className="px-5 py-10 text-center text-muted-foreground">
                          No errors recorded.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
