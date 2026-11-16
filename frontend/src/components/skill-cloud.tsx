"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";


interface SkillRow {
  skill: string;
  category: string | null;
  count: number;
  trend: number;
}

export function SkillCloud({ skills }: { skills: SkillRow[] }) {
  if (!skills.length) {
    return (
      <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        Skill trends appear once jobs have been classified.
      </div>
    );
  }

  const max = Math.max(...skills.map((s) => s.count), 1);

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {skills.map((skill) => {
        const ratio = skill.count / max;
        const rising = skill.trend > 15;
        const falling = skill.trend < -15;
        return (
          <Link
            key={skill.skill}
            href={`/jobs?skills=${encodeURIComponent(skill.skill)}`}
            className="group relative overflow-hidden rounded-lg border border-border bg-card px-3.5 py-3 transition-colors hover:border-primary/40"
          >
            <span
              aria-hidden
              className="absolute inset-y-0 left-0 bg-primary/[0.07] transition-all"
              style={{ width: `${Math.max(ratio * 100, 6)}%` }}
            />
            <span className="relative flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium">{skill.skill}</span>
              <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                <span>{skill.count}</span>
                {rising ? (
                  <ArrowUpRight className="size-3.5 text-success" />
                ) : falling ? (
                  <ArrowDownRight className="size-3.5 text-destructive" />
                ) : (
                  <Minus className="size-3.5 opacity-50" />
                )}
              </span>
            </span>
            {skill.category ? (
              <span className="relative mt-0.5 block text-[11px] text-muted-foreground">{skill.category}</span>
            ) : null}
          </Link>
        );
      })}
    </div>
  );
}
