import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "0";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(value >= 10_000 ? 0 : 1)}k`;
  return String(value);
}

export function formatCurrency(
  value: number | null | undefined,
  currency?: string | null,
  period?: string | null,
): string | null {
  if (value === null || value === undefined) return null;
  const symbol = currency === "INR" ? "₹" : currency === "USD" ? "$" : "";
  const suffix = period === "month" ? "/mo" : period === "year" ? "/yr" : "";
  if (value >= 1_000_000) {
    return `${symbol}${(value / 1_000_000).toFixed(1)}L${suffix}`;
  }
  if (value >= 1000) {
    return `${symbol}${Math.round(value / 1000)}K${suffix}`;
  }
  return `${symbol}${value}${suffix}`;
}

export function timeAgo(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const then = new Date(date).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return "—";
  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export const GEO_SCOPE_LABEL: Record<string, string> = {
  ahmedabad: "Ahmedabad",
  gujarat: "Gujarat",
  india_remote: "Remote (India)",
  india: "India",
  global: "Global / Remote",
  other: "Other locations",
};

export const VERIFICATION_LABEL: Record<string, string> = {
  verified: "Verified",
  unverified: "Unverified",
  stale: "Stale",
  expired: "Expired",
  rejected: "Rejected",
};
