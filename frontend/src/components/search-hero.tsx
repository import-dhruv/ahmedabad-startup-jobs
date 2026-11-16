"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const SUGGESTIONS = [
  "AI Engineer Ahmedabad",
  "Machine Learning Intern",
  "Python Developer Fresher",
  "Backend Engineer FastAPI",
  "Flutter Developer Internship",
  "Research Engineer AI",
];

export function SearchHero() {
  const router = useRouter();
  const [query, setQuery] = React.useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    router.push(`/jobs${params.toString() ? `?${params}` : ""}`);
  };

  return (
    <div className="mt-9">
      <form onSubmit={submit} className="mx-auto flex max-w-2xl items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Job title, company or skill — e.g. AI Engineer"
            aria-label="Search jobs"
            className="h-12 rounded-xl pl-10 pr-4 text-base shadow-sm"
          />
        </div>
        <Button type="submit" size="lg" className="h-12 shrink-0 px-5">
          Search
          <ArrowRight className="size-4" />
        </Button>
      </form>

      <div className="mt-3 flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => router.push(`/jobs?q=${encodeURIComponent(suggestion)}`)}
            className="rounded-full border border-border/80 bg-card/60 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
