"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Point {
  date: string;
  count: number;
}

export function TrendChart({ data }: { data: Point[] }) {
  const chartData = React.useMemo(
    () =>
      data.map((point) => ({
        ...point,
        label: new Date(point.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
      })),
    [data],
  );

  if (!chartData.length) {
    return (
      <div className="flex h-52 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
        No activity recorded yet.
      </div>
    );
  }

  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            minTickGap={24}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              fontSize: 12,
              boxShadow: "0 8px 24px rgb(0 0 0 / 0.12)",
            }}
            labelStyle={{ color: "var(--muted-foreground)" }}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="var(--primary)"
            strokeWidth={2}
            fill="url(#trendFill)"
            name="Openings"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
