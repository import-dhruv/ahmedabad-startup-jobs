"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, Search } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MultiSelect, Select } from "@/components/ui/select";
import { StartupCard } from "@/components/job-card";
import { startupsApi } from "@/lib/api";

export function StartupsExplorer() {
  const [query, setQuery] = React.useState("");
  const [industry, setIndustry] = React.useState<string[]>([]);
  const [city, setCity] = React.useState<string[]>([]);
  const [size, setSize] = React.useState<string[]>([]);
  const [funding, setFunding] = React.useState<string[]>([]);
  const [hiringOnly, setHiringOnly] = React.useState(false);
  const [sort, setSort] = React.useState("recent");

  const { data: filterData } = useQuery({ queryKey: ["startup-filters"], queryFn: startupsApi.filters });

  const { data, isLoading } = useQuery({
    queryKey: ["startups", query, industry, city, size, funding, hiringOnly, sort],
    queryFn: () =>
      startupsApi.list({
        q: query || undefined,
        industry: industry.length ? industry : undefined,
        city: city.length ? city : undefined,
        size_range: size.length ? size : undefined,
        funding_stage: funding.length ? funding : undefined,
        has_openings: hiringOnly || undefined,
        sort,
        limit: 60,
      }),
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="border-b border-border pb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          <Building2 className="size-6 text-primary" />
          Startup directory
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Every company the discovery engine has verified, with its headquarters, industry, funding stage
          and open roles. Headquarters is tracked separately from where each job is based.
        </p>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="relative lg:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search company, description or city"
            className="pl-9"
            aria-label="Search startups"
          />
        </div>
        <MultiSelect
          options={Object.entries(filterData?.industries ?? {}).map(([value, count]) => ({
            value,
            label: value,
            count,
          }))}
          values={industry}
          onValuesChange={setIndustry}
          placeholder="Industry"
        />
        <MultiSelect
          options={Object.entries(filterData?.cities ?? {}).map(([value, count]) => ({
            value,
            label: value,
            count,
          }))}
          values={city}
          onValuesChange={setCity}
          placeholder="Headquarters"
        />
        <Select
          options={[
            { value: "recent", label: "Recently discovered" },
            { value: "name", label: "Name A–Z" },
            { value: "openings", label: "Most openings" },
          ]}
          value={sort}
          onValueChange={setSort}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={hiringOnly}
            onChange={(event) => setHiringOnly(event.target.checked)}
            className="size-4 rounded border-input"
          />
          <span>Only companies with open roles</span>
        </label>
        {size.length || funding.length ? (
          <>
            <MultiSelect
              options={Object.entries(filterData?.size_ranges ?? {}).map(([value, count]) => ({
                value,
                label: value,
                count,
              }))}
              values={size}
              onValuesChange={setSize}
              placeholder="Team size"
              className="w-48"
            />
            <MultiSelect
              options={Object.entries(filterData?.funding_stages ?? {}).map(([value, count]) => ({
                value,
                label: value,
                count,
              }))}
              values={funding}
              onValuesChange={setFunding}
              placeholder="Funding stage"
              className="w-48"
            />
          </>
        ) : null}
        <span className="ml-auto text-sm text-muted-foreground">
          {data?.length ?? 0} startup{data?.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-8">
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Card key={index} className="h-52 animate-pulse" />
            ))}
          </div>
        ) : data?.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.map((startup) => (
              <StartupCard key={startup.id} startup={startup} />
            ))}
          </div>
        ) : (
          <Card className="p-12 text-center text-sm text-muted-foreground">
            No startups match those filters yet.
          </Card>
        )}
      </div>
    </div>
  );
}
