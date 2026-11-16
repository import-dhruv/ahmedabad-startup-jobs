"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Filter, LayoutGrid, List, Search, SlidersHorizontal, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { MultiSelect, Select } from "@/components/ui/select";
import { JobCard } from "@/components/job-card";
import { JobCardSkeleton } from "@/components/ui/skeleton";
import { jobsApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const SCOPE_OPTIONS = [
  { value: "ahmedabad", label: "Ahmedabad" },
  { value: "gujarat", label: "Rest of Gujarat" },
  { value: "india_remote", label: "Remote (India)" },
  { value: "india", label: "Elsewhere in India" },
  { value: "global", label: "Anywhere (remote)" },
];

const SORT_OPTIONS = [
  { value: "relevance", label: "Most relevant" },
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "salary_high", label: "Highest salary" },
  { value: "salary_low", label: "Lowest salary" },
  { value: "company", label: "Company A–Z" },
];

export function JobsExplorer() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [query, setQuery] = React.useState(searchParams.get("q") ?? "");
  const [filtersOpen, setFiltersOpen] = React.useState(false);

  const params = React.useMemo(() => {
    const next = new URLSearchParams(searchParams.toString());
    return next;
  }, [searchParams]);

  const queryString = params.toString();
  const queryKey = ["jobs", queryString];

  const { data, isLoading, isFetching } = useQuery({
    queryKey,
    queryFn: () => jobsApi.search(Object.fromEntries(params.entries())),
  });

  const filters = searchParams.getAll("skills");
  const experiences = searchParams.getAll("experience");
  const employmentTypes = searchParams.getAll("employment_type");
  const arrangements = searchParams.getAll("work_arrangement");
  const scopes = searchParams.getAll("scope");
  const cities = searchParams.getAll("city");
  const industries = searchParams.getAll("industry");
  const remote = searchParams.get("remote") === "true";
  const internship = searchParams.get("internship") === "true";
  const minSalary = searchParams.get("min_salary") ?? "";
  const maxSalary = searchParams.get("max_salary") ?? "";
  const sort = searchParams.get("sort") ?? "relevance";
  const page = Number(searchParams.get("page") ?? "1");

  const update = React.useCallback(
    (mutate: (next: URLSearchParams) => void, resetPage = true) => {
      const next = new URLSearchParams(searchParams.toString());
      mutate(next);
      if (resetPage) next.delete("page");
      const query = next.toString();
      router.replace(query ? `/jobs?${query}` : "/jobs", { scroll: false });
    },
    [router, searchParams],
  );

  const toggleIn = (key: string, value: string) => {
    update((next) => {
      const existing = next.getAll(key);
      next.delete(key);
      const updated = existing.includes(value)
        ? existing.filter((v) => v !== value)
        : [...existing, value];
      updated.forEach((v) => next.append(key, v));
    });
  };

  const setValue = (key: string, value: string | null) => {
    update((next) => {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    });
  };

  const onSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setValue("q", query.trim() || null);
  };

  const activeFilterCount =
    filters.length +
    experiences.length +
    employmentTypes.length +
    arrangements.length +
    scopes.length +
    cities.length +
    industries.length +
    (remote ? 1 : 0) +
    (internship ? 1 : 0) +
    (minSalary ? 1 : 0) +
    (maxSalary ? 1 : 0);

  const clearAll = () => {
    router.replace("/jobs");
    setQuery("");
  };

  const facetOptions = data?.facets;

  const filterPanel = (
    <div className="space-y-5">
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Location scope
        </h3>
        <div className="space-y-1.5">
          {SCOPE_OPTIONS.map((option) => (
            <label key={option.value} className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox
                checked={scopes.includes(option.value)}
                onCheckedChange={() => toggleIn("scope", option.value)}
              />
              <span>{option.label}</span>
              {facetOptions?.geo_scopes?.[option.label] ? (
                <span className="ml-auto text-xs text-muted-foreground">
                  {facetOptions.geo_scopes[option.label]}
                </span>
              ) : null}
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Experience level
        </h3>
        <div className="space-y-1.5">
          {["Fresher", "0-1 years", "1-3 years", "3-5 years", "5-8 years", "8+ years"].map((level) => (
            <label key={level} className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox
                checked={experiences.includes(level)}
                onCheckedChange={() => toggleIn("experience", level)}
              />
              <span>{level}</span>
              {facetOptions?.experience_levels?.[level] ? (
                <span className="ml-auto text-xs text-muted-foreground">
                  {facetOptions.experience_levels[level]}
                </span>
              ) : null}
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Employment type
        </h3>
        <div className="space-y-1.5">
          {["Full-time", "Part-time", "Internship", "Contract", "Freelance", "Apprenticeship"].map((type) => (
            <label key={type} className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox
                checked={employmentTypes.includes(type)}
                onCheckedChange={() => toggleIn("employment_type", type)}
              />
              <span>{type}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Work arrangement
        </h3>
        <div className="space-y-1.5">
          {["On-site", "Hybrid", "Remote"].map((arrangement) => (
            <label key={arrangement} className="flex cursor-pointer items-center gap-2 text-sm">
              <Checkbox
                checked={arrangements.includes(arrangement)}
                onCheckedChange={() => toggleIn("work_arrangement", arrangement)}
              />
              <span>{arrangement}</span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Skills</h3>
        <MultiSelect
          options={(facetOptions?.skills ?? []).map((skill) => ({
            value: skill.name,
            label: skill.name,
            count: skill.count,
          }))}
          values={filters}
          onValuesChange={(values) =>
            update((next) => {
              next.delete("skills");
              values.forEach((v) => next.append("skills", v));
            })
          }
          placeholder="Filter by skill"
        />
      </div>

      {facetOptions?.cities && Object.keys(facetOptions.cities).length ? (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">City</h3>
          <MultiSelect
            options={Object.entries(facetOptions.cities).map(([city, count]) => ({
              value: city,
              label: city,
              count,
            }))}
            values={cities}
            onValuesChange={(values) =>
              update((next) => {
                next.delete("city");
                values.forEach((v) => next.append("city", v));
              })
            }
            placeholder="Filter by city"
          />
        </div>
      ) : null}

      {facetOptions?.industries && Object.keys(facetOptions.industries).length ? (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Industry
          </h3>
          <MultiSelect
            options={Object.entries(facetOptions.industries).map(([industry, count]) => ({
              value: industry,
              label: industry,
              count,
            }))}
            values={industries}
            onValuesChange={(values) =>
              update((next) => {
                next.delete("industry");
                values.forEach((v) => next.append("industry", v));
              })
            }
            placeholder="Filter by industry"
          />
        </div>
      ) : null}

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Salary range
        </h3>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min={0}
            placeholder="Min"
            defaultValue={minSalary}
            onBlur={(event) => setValue("min_salary", event.target.value || null)}
          />
          <span className="text-muted-foreground">–</span>
          <Input
            type="number"
            min={0}
            placeholder="Max"
            defaultValue={maxSalary}
            onBlur={(event) => setValue("max_salary", event.target.value || null)}
          />
        </div>
        <p className="mt-1.5 text-[11px] text-muted-foreground">Annual, in the listing&apos;s own currency.</p>
      </div>

      <div className="space-y-1.5 border-t border-border pt-4">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <Checkbox checked={remote} onCheckedChange={() => setValue("remote", remote ? null : "true")} />
          <span>Remote only</span>
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <Checkbox
            checked={internship}
            onCheckedChange={() => setValue("internship", internship ? null : "true")}
          />
          <span>Internships only</span>
        </label>
      </div>

      {activeFilterCount > 0 ? (
        <Button variant="ghost" size="sm" onClick={clearAll} className="w-full">
          <X className="size-4" /> Clear all filters
        </Button>
      ) : null}
    </div>
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Startup job openings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {isLoading
              ? "Searching…"
              : `${data?.total ?? 0} opening${data?.total === 1 ? "" : "s"} match your filters`}
            {!isLoading && data ? ` · page ${data.page} of ${data.pages}` : ""}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <form onSubmit={onSearch} className="flex min-w-[16rem] flex-1 items-center gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search title, company or skill"
                className="pl-9"
                aria-label="Search jobs"
              />
            </div>
            <Button type="submit" variant="secondary">
              Search
            </Button>
          </form>

          <Button
            variant="outline"
            className="lg:hidden"
            onClick={() => setFiltersOpen((open) => !open)}
          >
            <SlidersHorizontal className="size-4" /> Filters
            {activeFilterCount > 0 ? (
              <Badge variant="default" className="ml-1">
                {activeFilterCount}
              </Badge>
            ) : null}
          </Button>

          <Select
            options={SORT_OPTIONS}
            value={sort}
            onValueChange={(value) => setValue("sort", value)}
            className="w-44"
          />
        </div>
      </div>

      {activeFilterCount > 0 ? (
        <div className="flex flex-wrap items-center gap-2 py-4">
          {[
            ...filters.map((value) => ({ key: "skills", value, label: value })),
            ...experiences.map((value) => ({ key: "experience", value, label: value })),
            ...employmentTypes.map((value) => ({ key: "employment_type", value, label: value })),
            ...arrangements.map((value) => ({ key: "work_arrangement", value, label: value })),
            ...scopes.map((value) => ({
              key: "scope",
              value,
              label: SCOPE_OPTIONS.find((s) => s.value === value)?.label ?? value,
            })),
            ...cities.map((value) => ({ key: "city", value, label: value })),
            ...industries.map((value) => ({ key: "industry", value, label: value })),
          ].map((chip) => (
            <button
              key={`${chip.key}-${chip.value}`}
              type="button"
              onClick={() => toggleIn(chip.key, chip.value)}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-xs transition-colors hover:border-primary/40"
            >
              {chip.label}
              <X className="size-3" />
            </button>
          ))}
          {remote ? (
            <button
              type="button"
              onClick={() => setValue("remote", null)}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-xs hover:border-primary/40"
            >
              Remote only <X className="size-3" />
            </button>
          ) : null}
          {internship ? (
            <button
              type="button"
              onClick={() => setValue("internship", null)}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-xs hover:border-primary/40"
            >
              Internships only <X className="size-3" />
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="hidden lg:block">
          <Card className="sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto">
            <CardContent className="p-5 scrollbar-thin">
              <div className="mb-4 flex items-center gap-2">
                <Filter className="size-4" />
                <h2 className="text-sm font-semibold">Filters</h2>
              </div>
              {filterPanel}
            </CardContent>
          </Card>
        </aside>

        {filtersOpen ? (
          <Card className="lg:hidden">
            <CardContent className="p-5">{filterPanel}</CardContent>
          </Card>
        ) : null}

        <div className="space-y-3">
          {isLoading ? (
            <>
              <JobCardSkeleton />
              <JobCardSkeleton />
              <JobCardSkeleton />
            </>
          ) : data?.items?.length ? (
            <>
              {data.items.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}

              {data.pages > 1 ? (
                <div className="flex items-center justify-center gap-3 pt-6">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setValue("page", String(page - 1))}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {data.page} of {data.pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= data.pages}
                    onClick={() => setValue("page", String(page + 1))}
                  >
                    Next
                  </Button>
                </div>
              ) : null}
            </>
          ) : (
            <Card className="p-12 text-center">
              <LayoutGrid className="mx-auto size-8 text-muted-foreground/50" />
              <h3 className="mt-4 text-base font-semibold">No openings match these filters</h3>
              <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
                Try widening the location scope — Ahmedabad, Gujarat, remote-in-India, or anywhere.
              </p>
              <Button variant="outline" className="mt-5" onClick={clearAll}>
                Reset filters
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
