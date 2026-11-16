"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  Bookmark,
  Briefcase,
  CheckCircle2,
  Plus,
  Sparkles,
  Target,
  Trash2,
  Upload,
  User,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JobCard } from "@/components/job-card";
import { useAuth } from "@/components/auth-provider";
import { API_URL, userApi, type Profile } from "@/lib/api";

const EMPLOYMENT_OPTIONS = ["Full-time", "Internship", "Part-time", "Contract", "Freelance"];
const ARRANGEMENT_OPTIONS = ["Remote", "Hybrid", "On-site"];
const LOCATION_OPTIONS = ["Ahmedabad", "Gandhinagar", "GIFT City", "Sanand", "Surat", "Vadodara"];

export function CandidateDashboard() {
  const router = useRouter();
  const { user, token, loading } = useAuth();
  const [profile, setProfile] = React.useState<Profile | null>(null);
  const [headline, setHeadline] = React.useState("");
  const [bio, setBio] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [experienceYears, setExperienceYears] = React.useState("");
  const [skillsText, setSkillsText] = React.useState("");
  const [preferredTypes, setPreferredTypes] = React.useState<string[]>([]);
  const [preferredLocations, setPreferredLocations] = React.useState<string[]>([]);
  const [preferredArrangements, setPreferredArrangements] = React.useState<string[]>([]);
  const [saving, setSaving] = React.useState(false);
  const [alertName, setAlertName] = React.useState("");
  const [alertQuery, setAlertQuery] = React.useState("");

  React.useEffect(() => {
    if (!loading && !user) router.replace("/login?next=/dashboard");
  }, [loading, user, router]);

  React.useEffect(() => {
    if (!token) return;
    userApi
      .profile(token)
      .then((data) => {
        setProfile(data);
        setHeadline(data.headline ?? "");
        setBio(data.bio ?? "");
        setLocation(data.location ?? "");
        setExperienceYears(data.experience_years?.toString() ?? "");
        setSkillsText(data.skills.join(", "));
        setPreferredTypes(data.preferred_job_types);
        setPreferredLocations(data.preferred_locations);
        setPreferredArrangements(data.preferred_arrangements);
      })
      .catch(() => undefined);
  }, [token]);

  const recommendations = useQuery({
    queryKey: ["recommendations", token],
    queryFn: () => userApi.recommendations(token!),
    enabled: Boolean(token),
  });

  const savedJobs = useQuery({
    queryKey: ["saved-jobs", token],
    queryFn: () => userApi.savedJobs(token!),
    enabled: Boolean(token),
  });

  const alerts = useQuery({
    queryKey: ["alerts", token],
    queryFn: () => userApi.alerts(token!),
    enabled: Boolean(token),
  });

  const applications = useQuery({
    queryKey: ["applications", token],
    queryFn: () => userApi.applications(token!),
    enabled: Boolean(token),
  });

  const notifications = useQuery({
    queryKey: ["notifications", token],
    queryFn: () => userApi.notifications(token!),
    enabled: Boolean(token),
  });

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    try {
      const updated = await userApi.updateProfile(token, {
        headline: headline || null,
        bio: bio || null,
        location: location || null,
        experience_years: experienceYears ? Number(experienceYears) : null,
        skills: skillsText
          .split(",")
          .map((skill) => skill.trim())
          .filter(Boolean),
        preferred_job_types: preferredTypes,
        preferred_locations: preferredLocations,
        preferred_arrangements: preferredArrangements,
      });
      setProfile(updated);
      toast.success("Profile updated — recommendations refreshed");
    } catch {
      toast.error("Could not save your profile");
    } finally {
      setSaving(false);
    }
  };

  const uploadResume = async (file: File) => {
    if (!token) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API_URL}/me/profile/resume`, {
        method: "POST",
        body: form,
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("upload failed");
      toast.success("Resume uploaded");
    } catch {
      toast.error("Could not upload the resume");
    }
  };

  const createAlert = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token || alertName.trim().length < 2) return;
    try {
      await userApi.createAlert(token, {
        name: alertName.trim(),
        query: alertQuery.trim() || undefined,
        filters: {},
        frequency: "instant",
      });
      setAlertName("");
      setAlertQuery("");
      await alerts.refetch();
      toast.success("Alert created");
    } catch {
      toast.error("Could not create the alert");
    }
  };

  const removeAlert = async (id: string) => {
    if (!token) return;
    await userApi.deleteAlert(token, id);
    await alerts.refetch();
  };

  const toggle = (list: string[], value: string, setter: (next: string[]) => void) => {
    setter(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-16 text-center text-sm text-muted-foreground">Loading…</div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {user.full_name ? `Hi, ${user.full_name.split(" ")[0]}` : "Your dashboard"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {recommendations.data?.profile_complete
              ? "Recommendations are scored against your profile."
              : "Add your skills and experience to unlock scored recommendations."}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/jobs">Browse all jobs</Link>
        </Button>
      </div>

      <Tabs defaultValue="matches" className="mt-6">
        <TabsList>
          <TabsTrigger value="matches">
            <Target className="mr-1.5 size-4" /> Matches
          </TabsTrigger>
          <TabsTrigger value="saved">
            <Bookmark className="mr-1.5 size-4" /> Saved
          </TabsTrigger>
          <TabsTrigger value="alerts">
            <Bell className="mr-1.5 size-4" /> Alerts
          </TabsTrigger>
          <TabsTrigger value="applications">
            <Briefcase className="mr-1.5 size-4" /> Applications
          </TabsTrigger>
          <TabsTrigger value="profile">
            <User className="mr-1.5 size-4" /> Profile
          </TabsTrigger>
        </TabsList>

        <TabsContent value="matches">
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="space-y-3">
              {recommendations.isLoading ? (
                <Card className="h-40 animate-pulse" />
              ) : recommendations.data?.items?.length ? (
                recommendations.data.items.map(({ job, match }) => (
                  <div key={job.id} className="relative">
                    <JobCard job={job} />
                    <div className="pointer-events-none absolute right-4 top-4">
                      <Badge variant="success" className="gap-1">
                        <Sparkles className="size-3" /> {Math.round(match.score)}% match
                      </Badge>
                    </div>
                    {match.reasons.length ? (
                      <p className="mt-1 px-1 text-xs text-muted-foreground">{match.reasons.join(" · ")}</p>
                    ) : null}
                  </div>
                ))
              ) : (
                <Card className="p-10 text-center text-sm text-muted-foreground">
                  Complete your profile to see matched openings.
                </Card>
              )}
            </div>

            <aside className="space-y-4">
              <Card>
                <CardContent className="p-5">
                  <h3 className="text-sm font-semibold">Notifications</h3>
                  <ul className="mt-3 space-y-2.5">
                    {notifications.data?.slice(0, 6).map((notification) => (
                      <li key={notification.id} className="border-l-2 border-primary/50 pl-3">
                        <p className="text-sm font-medium">{notification.title}</p>
                        {notification.body ? (
                          <p className="text-xs text-muted-foreground">{notification.body}</p>
                        ) : null}
                      </li>
                    ))}
                    {!notifications.data?.length ? (
                      <li className="text-sm text-muted-foreground">
                        No notifications yet — create an alert to get started.
                      </li>
                    ) : null}
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-5">
                  <h3 className="text-sm font-semibold">How matching works</h3>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    Your score combines skill overlap with the job, experience compatibility, preferred
                    employment type, work arrangement and location. Nothing is hidden — the reasons are
                    shown on each match.
                  </p>
                </CardContent>
              </Card>
            </aside>
          </div>
        </TabsContent>

        <TabsContent value="saved">
          {savedJobs.data?.items?.length ? (
            <div className="space-y-3">
              {savedJobs.data.items.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          ) : (
            <Card className="p-10 text-center text-sm text-muted-foreground">
              You have not saved any jobs yet.
            </Card>
          )}
        </TabsContent>

        <TabsContent value="alerts">
          <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
            <div className="space-y-3">
              {alerts.data?.length ? (
                alerts.data.map((alert) => (
                  <Card key={alert.id}>
                    <CardContent className="flex items-start justify-between gap-4 p-5">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold">{alert.name}</h3>
                          <Badge variant={alert.is_active ? "success" : "outline"}>
                            {alert.is_active ? "Active" : "Paused"}
                          </Badge>
                          <Badge variant="secondary">{alert.frequency}</Badge>
                        </div>
                        {alert.query ? (
                          <p className="mt-1 text-sm text-muted-foreground">
                            Notify me whenever a new <span className="text-foreground">{alert.query}</span> job
                            appears.
                          </p>
                        ) : null}
                        <p className="mt-1 text-xs text-muted-foreground">
                          Last triggered: {alert.last_triggered_at ?? "never"}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => removeAlert(alert.id)}
                        aria-label="Delete alert"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Card className="p-10 text-center text-sm text-muted-foreground">
                  No alerts yet. Create one to be notified when a matching role opens.
                </Card>
              )}
            </div>

            <Card className="h-fit">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">New alert</h3>
                <form onSubmit={createAlert} className="mt-3 space-y-3">
                  <div className="space-y-1.5">
                    <label htmlFor="alert-name" className="text-sm font-medium">
                      Name
                    </label>
                    <Input
                      id="alert-name"
                      required
                      minLength={2}
                      value={alertName}
                      onChange={(event) => setAlertName(event.target.value)}
                      placeholder="AI Engineer roles"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="alert-query" className="text-sm font-medium">
                      Keywords
                    </label>
                    <Input
                      id="alert-query"
                      value={alertQuery}
                      onChange={(event) => setAlertQuery(event.target.value)}
                      placeholder="AI Engineer"
                    />
                    <p className="text-[11px] text-muted-foreground">
                      We match new openings whose title, company or skills contain these words.
                    </p>
                  </div>
                  <Button type="submit" className="w-full">
                    <Plus className="size-4" /> Create alert
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="applications">
          {applications.data?.length ? (
            <div className="space-y-2">
              {applications.data.map((application) => (
                <Card key={application.id}>
                  <CardContent className="flex items-center justify-between gap-4 p-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {applications.data.length ? `Application #${application.id.slice(0, 8)}` : ""}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Status: <span className="capitalize">{application.status}</span>
                        {application.applied_at ? ` · ${new Date(application.applied_at).toLocaleDateString()}` : ""}
                      </p>
                    </div>
                    <Badge
                      variant={
                        application.status === "offer"
                          ? "success"
                          : application.status === "rejected"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {application.status}
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="p-10 text-center text-sm text-muted-foreground">
              Track applications here — mark a job as applied when you submit an application.
            </Card>
          )}
        </TabsContent>

        <TabsContent value="profile">
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <Card>
              <CardContent className="p-6">
                <h2 className="text-lg font-semibold tracking-tight">Candidate profile</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  This profile powers your job matches. Nothing here is shared with employers.
                </p>

                <form onSubmit={saveProfile} className="mt-6 space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <label htmlFor="headline" className="text-sm font-medium">
                        Headline
                      </label>
                      <Input
                        id="headline"
                        value={headline}
                        onChange={(event) => setHeadline(event.target.value)}
                        placeholder="Backend engineer · Python & FastAPI"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label htmlFor="location" className="text-sm font-medium">
                        Location
                      </label>
                      <Input
                        id="location"
                        value={location}
                        onChange={(event) => setLocation(event.target.value)}
                        placeholder="Ahmedabad, Gujarat"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="experience" className="text-sm font-medium">
                      Years of experience
                    </label>
                    <Input
                      id="experience"
                      type="number"
                      min={0}
                      max={40}
                      step={0.5}
                      value={experienceYears}
                      onChange={(event) => setExperienceYears(event.target.value)}
                      placeholder="2"
                      className="w-40"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="skills" className="text-sm font-medium">
                      Skills
                    </label>
                    <Textarea
                      id="skills"
                      value={skillsText}
                      onChange={(event) => setSkillsText(event.target.value)}
                      placeholder="Python, FastAPI, PostgreSQL, Docker"
                    />
                    <p className="text-[11px] text-muted-foreground">Separate skills with commas.</p>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="bio" className="text-sm font-medium">
                      About you
                    </label>
                    <Textarea
                      id="bio"
                      value={bio}
                      onChange={(event) => setBio(event.target.value)}
                      placeholder="A short summary of what you are looking for"
                    />
                  </div>

                  <fieldset>
                    <legend className="text-sm font-medium">Preferred job types</legend>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {EMPLOYMENT_OPTIONS.map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => toggle(preferredTypes, option, setPreferredTypes)}
                          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                            preferredTypes.includes(option)
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  </fieldset>

                  <fieldset>
                    <legend className="text-sm font-medium">Preferred work arrangement</legend>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {ARRANGEMENT_OPTIONS.map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => toggle(preferredArrangements, option, setPreferredArrangements)}
                          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                            preferredArrangements.includes(option)
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  </fieldset>

                  <fieldset>
                    <legend className="text-sm font-medium">Preferred locations</legend>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {LOCATION_OPTIONS.map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => toggle(preferredLocations, option, setPreferredLocations)}
                          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                            preferredLocations.includes(option)
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  </fieldset>

                  <Button type="submit" disabled={saving}>
                    {saving ? "Saving…" : "Save profile"}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="h-fit">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold">Resume</h3>
                {profile?.resume_filename ? (
                  <p className="mt-2 inline-flex items-center gap-1.5 text-sm text-success">
                    <CheckCircle2 className="size-4" /> {profile.resume_filename}
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-muted-foreground">No resume uploaded yet.</p>
                )}
                <label className="mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
                  <Upload className="size-4" />
                  Upload resume (pdf, doc, txt · max 5MB)
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx,.txt,.rtf"
                    className="sr-only"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) uploadResume(file);
                    }}
                  />
                </label>
                <p className="mt-3 text-[11px] text-muted-foreground">
                  Your resume stays on the platform and is never shared with employers.
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
