/**
 * The browser talks to a same-origin `/api/v1` path, which Next.js proxies to
 * the API server (see `API_PROXY_TARGET` in next.config.ts). That keeps the
 * backend location a runtime setting instead of a build-time constant, and
 * avoids cross-origin requests in the browser.
 *
 * Set `NEXT_PUBLIC_API_URL` to call the API directly instead — useful when
 * the API is on a different origin and CORS is configured.
 */
export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL?.trim() || "/api/v1"
).replace(/\/$/, "");

/**
 * Absolute base URL for server-side rendering, where a relative path has no
 * meaning. Falls back to the local API during development.
 */
export const API_SERVER_URL = (
  process.env.API_PROXY_TARGET?.trim()
    ? `${process.env.API_PROXY_TARGET.trim().replace(/\/$/, "")}/api/v1`
    : process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000/api/v1"
).replace(/\/$/, "");

/** Browser requests are same-origin (proxied); server requests need an absolute URL. */
function resolveBase(): string {
  return typeof window === "undefined" ? API_SERVER_URL : API_URL;
}

export interface ApiError {
  status: number;
  detail: string;
}

export class ApiRequestError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = "ApiRequestError";
  }
}

async function request<T>(path: string, init?: RequestInit & { token?: string | null }): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  // The development tunnel is an ngrok free-plan endpoint. Without this
  // documented header ngrok serves an HTML interstitial (with status 200)
  // instead of the API response when the request comes from a browser, which
  // makes res.json() throw. It is ignored by non-ngrok origins.
  headers.set("ngrok-skip-browser-warning", "true");
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (init?.token) {
    headers.set("Authorization", `Bearer ${init.token}`);
  }

  const res = await fetch(`${resolveBase()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiRequestError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, token?: string | null) => request<T>(path, { method: "GET", token }),
  post: <T>(path: string, body?: unknown, token?: string | null) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), token }),
  patch: <T>(path: string, body?: unknown, token?: string | null) =>
    request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body), token }),
  delete: <T>(path: string, token?: string | null) => request<T>(path, { method: "DELETE", token }),
  postForm: async <T>(path: string, form: FormData, token?: string | null): Promise<T> => {
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${resolveBase()}${path}`, { method: "POST", body: form, headers });
    if (!res.ok) throw new ApiRequestError(res.status, `Upload failed (${res.status})`);
    return (await res.json()) as T;
  },
};

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface Location {
  raw: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  scope: string;
  is_remote: boolean;
}

export interface Salary {
  min: number | null;
  max: number | null;
  currency: string | null;
  period: string | null;
  disclosed: boolean;
}

export interface CompanyRef {
  id: string | null;
  name: string;
  slug: string | null;
  logo_url: string | null;
  industry: string | null;
  hq_city: string | null;
}

export interface SourceRef {
  id: string;
  name: string;
  slug: string;
  connector_type: string;
  base_url: string | null;
  is_active: boolean;
  last_success_at: string | null;
}

export interface JobSummary {
  id: string;
  slug: string;
  title: string;
  company: CompanyRef;
  location: Location;
  employment_type: string | null;
  work_arrangement: string | null;
  experience_level: string | null;
  salary: Salary;
  posted_at: string | null;
  last_verified_at: string | null;
  discovered_at: string | null;
  apply_url: string;
  original_url: string;
  source: SourceRef | null;
  verification_status: string;
  status: string;
  quality_score: number;
  skills: string[];
  categories: string[];
  geo_scope: string;
  is_remote: boolean;
  ai_summary: string | null;
}

export interface JobDetail extends JobSummary {
  description: string | null;
  responsibilities: string[];
  qualifications: string[];
  skills_text: string | null;
  department: string | null;
  deadline: string | null;
  references: {
    id: string;
    source_url: string;
    first_seen_at: string | null;
    last_seen_at: string | null;
    is_primary: boolean;
  }[];
  startup: StartupSummary | null;
}

export interface JobListResponse {
  items: JobSummary[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  facets: {
    industries?: Record<string, number>;
    skills?: { name: string; category: string | null; count: number }[];
    cities?: Record<string, number>;
    geo_scopes?: Record<string, number>;
    employment_types?: Record<string, number>;
    experience_levels?: Record<string, number>;
    work_arrangements?: Record<string, number>;
  };
}

export interface StartupSummary {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  website: string | null;
  linkedin_url?: string | null;
  description?: string | null;
  industry: string;
  hq_city: string | null;
  hq_state?: string | null;
  hq_country?: string | null;
  founded_year?: number | null;
  size_range: string | null;
  hiring_status: string;
  careers_url?: string | null;
  tech_stack: string[];
  funding_stage: string | null;
  verification_status: string;
  last_verified_at: string | null;
  active_job_count: number;
  created_at: string;
}

export interface StartupDetail extends StartupSummary {
  founders: { id: string; name: string; title: string | null; linkedin_url: string | null }[];
  funding_rounds: {
    id: string;
    round_type: string;
    amount: string | null;
    currency: string | null;
    announced_date: string | null;
    investors: string[];
    source_url: string | null;
    is_verified: boolean;
  }[];
  recent_jobs: JobSummary[];
}

export interface DashboardStats {
  total_startups: number;
  total_active_jobs: number;
  new_jobs_24h: number;
  new_jobs_7d: number;
  new_jobs_30d: number;
  companies_hiring: number;
  internship_openings: number;
  remote_opportunities: number;
  ahmedabad_jobs: number;
  gujarat_jobs: number;
  total_sources: number;
  active_sources: number;
  jobs_awaiting_verification: number;
  expired_jobs: number;
  last_sync_at: string | null;
  last_discovered_company_at: string | null;
  generated_at: string;
}

export interface JobFilters {
  employment_types: string[];
  experience_levels: string[];
  work_arrangements: string[];
  job_categories: string[];
  skills: { name: string; count: number }[];
  all_skills: string[];
  cities: { city: string; count: number }[];
  industries: Record<string, number>;
  geo_scopes: Record<string, string>;
  sort_options: string[];
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Profile {
  id: string;
  user_id: string;
  headline: string | null;
  bio: string | null;
  location: string | null;
  phone: string | null;
  resume_url: string | null;
  resume_filename: string | null;
  experience_years: number | null;
  skills: string[];
  preferred_job_types: string[];
  preferred_locations: string[];
  preferred_arrangements: string[];
  open_to_remote: boolean;
  expected_salary_min: number | null;
  expected_salary_max: number | null;
  github_url: string | null;
  linkedin_url: string | null;
  portfolio_url: string | null;
}

/* ------------------------------------------------------------------ */
/* Endpoints                                                           */
/* ------------------------------------------------------------------ */

export const jobsApi = {
  search: (params: Record<string, string | number | boolean | string[] | undefined>) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === "" || value === false) return;
      if (Array.isArray(value)) {
        value.forEach((v) => search.append(key, v));
      } else {
        search.append(key, String(value));
      }
    });
    return api.get<JobListResponse>(`/jobs?${search.toString()}`);
  },
  detail: (id: string, token?: string | null) => api.get<JobDetail>(`/jobs/${id}`, token),
  bySlug: (slug: string) => api.get<JobDetail>(`/jobs/slug/${slug}`),
  filters: () => api.get<JobFilters>("/jobs/filters"),
};

export const startupsApi = {
  list: (params: Record<string, string | number | boolean | string[] | undefined> = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === "" || value === false) return;
      if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
      else search.append(key, String(value));
    });
    return api.get<StartupSummary[]>(`/startups?${search.toString()}`);
  },
  bySlug: (slug: string) => api.get<StartupDetail>(`/startups/slug/${slug}`),
  filters: () =>
    api.get<{
      industries: Record<string, number>;
      funding_stages: Record<string, number>;
      size_ranges: Record<string, number>;
      cities: Record<string, number>;
      hiring_statuses: string[];
    }>("/startups/filters"),
};

export const statsApi = {
  dashboard: () => api.get<DashboardStats>("/stats/dashboard"),
  trends: (days = 30) => api.get<{ days: number; series: { date: string; count: number }[] }>(`/stats/trends?days=${days}`),
  skills: () => api.get<{ skills: { skill: string; category: string | null; count: number; trend: number }[] }>("/stats/skills"),
  industries: () => api.get<{ industries: { industry: string; count: number; companies: number }[] }>("/stats/industries"),
  hiring: () =>
    api.get<{ companies: { startup_id: string; name: string; openings: number; logo_url: string | null; slug: string | null; industry: string | null }[] }>(
      "/stats/hiring",
    ),
  mix: () =>
    api.get<{
      employment_types: { label: string; value: number }[];
      experience_levels: { label: string; value: number }[];
      locations: { label: string; value: number; scope: string }[];
      sources: { label: string; value: number }[];
    }>("/stats/mix"),
  insights: () =>
    api.get<{ key: string; label: string; value: number; detail: string | null; measured: boolean }[]>(
      "/stats/insights",
    ),
  aiInsights: () =>
    api.get<{ available: boolean; reason?: string; interpretations: string[] }>("/stats/ai-insights"),
  recentJobs: (limit = 12) => api.get<{ items: JobSummary[] }>(`/stats/recent-jobs?limit=${limit}`),
  recentStartups: (limit = 12) =>
    api.get<{ items: (StartupSummary & { created_at: string })[] }>(`/stats/recent-startups?limit=${limit}`),
};

export const authApi = {
  register: (body: { email: string; password: string; full_name?: string }) =>
    api.post<{ access_token: string; refresh_token: string; token_type: string; expires_in: number; user: User }>(
      "/auth/register",
      body,
    ),
  login: (body: { email: string; password: string }) =>
    api.post<{ access_token: string; refresh_token: string; token_type: string; expires_in: number; user: User }>(
      "/auth/login",
      body,
    ),
  me: (token: string) => api.get<User>("/auth/me", token),
  googleConfig: () =>
    api.get<{ enabled: boolean; client_id: string | null; redirect_uri: string | null; authorization_url: string }>(
      "/auth/google/config",
    ),
  googleSignIn: (idToken: string) =>
    api.post<{ access_token: string; refresh_token: string; token_type: string; expires_in: number; user: User }>(
      "/auth/google",
      { id_token: idToken },
    ),
};

export const userApi = {
  profile: (token: string) => api.get<Profile>("/me/profile", token),
  updateProfile: (token: string, body: Partial<Profile>) => api.patch<Profile>("/me/profile", body, token),
  savedJobs: (token: string) => api.get<{ items: JobSummary[]; total: number }>("/me/saved-jobs", token),
  saveJob: (token: string, jobId: string) => api.post(`/me/saved-jobs/${jobId}`, undefined, token),
  unsaveJob: (token: string, jobId: string) => api.delete(`/me/saved-jobs/${jobId}`, token),
  savedStartups: (token: string) =>
    api.get<{ id: string; name: string; slug: string; logo_url: string | null; website: string | null; industry: string; hq_city: string | null; active_job_count: number }[]>(
      "/me/saved-startups",
      token,
    ),
  saveStartup: (token: string, id: string) => api.post(`/me/saved-startups/${id}`, undefined, token),
  unsaveStartup: (token: string, id: string) => api.delete(`/me/saved-startups/${id}`, token),
  alerts: (token: string) =>
    api.get<{ id: string; name: string; query: string | null; filters: Record<string, unknown>; frequency: string; is_active: boolean; last_triggered_at: string | null; created_at: string }[]>(
      "/me/alerts",
      token,
    ),
  createAlert: (token: string, body: { name: string; query?: string; filters?: Record<string, unknown>; frequency?: string }) =>
    api.post("/me/alerts", body, token),
  deleteAlert: (token: string, id: string) => api.delete(`/me/alerts/${id}`, token),
  applications: (token: string) =>
    api.get<{ id: string; job_id: string; status: string; notes: string | null; applied_at: string | null; created_at: string }[]>(
      "/me/applications",
      token,
    ),
  createApplication: (token: string, body: { job_id: string; status?: string; notes?: string }) =>
    api.post("/me/applications", body, token),
  recommendations: (token: string) =>
    api.get<{
      items: { job: JobSummary; match: { score: number; matched_skills: string[]; missing_skills: string[]; reasons: string[] } }[];
      profile_complete: boolean;
      note: string;
    }>("/me/recommendations", token),
  notifications: (token: string) =>
    api.get<{ id: string; type: string; title: string; body: string | null; link: string | null; is_read: boolean; created_at: string }[]>(
      "/me/notifications",
      token,
    ),
};
