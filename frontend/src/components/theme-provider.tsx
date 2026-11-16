"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "ahsj-theme";

/**
 * The theme lives outside React (localStorage + the OS preference), so it is
 * read through `useSyncExternalStore` rather than mirrored into state inside
 * an effect. That keeps the DOM in sync without a cascading render and
 * without a hydration mismatch.
 */
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

function readTheme(): Theme {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
  return stored === "light" || stored === "dark" ? stored : "system";
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    media.removeEventListener("change", onChange);
    window.removeEventListener("storage", onChange);
  };
}

function systemPrefersDark() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = React.useSyncExternalStore(subscribe, readTheme, () => "system" as Theme);

  React.useEffect(() => {
    const dark = theme === "dark" || (theme === "system" && systemPrefersDark());
    document.documentElement.classList.toggle("dark", dark);
  }, [theme]);

  const setTheme = React.useCallback((next: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    notify();
  }, []);

  const context = React.useMemo(() => ({ theme, setTheme }), [theme, setTheme]);

  return <ThemeContext.Provider value={context}>{children}</ThemeContext.Provider>;
}

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = React.createContext<ThemeContextValue>({
  theme: "system",
  setTheme: () => undefined,
});

export function useTheme() {
  return React.useContext(ThemeContext);
}

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  // Read the resolved state from the DOM on the client so the icon matches
  // the rendered theme without a mount effect.
  const isDark = React.useSyncExternalStore(
    subscribe,
    () => document.documentElement.classList.contains("dark"),
    () => false,
  );

  const toggle = () => {
    const next = isDark ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle theme"
      title={`Theme: ${theme}`}
      className="inline-flex size-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      {isDark ? <Moon className="size-4" /> : <Sun className="size-4" />}
    </button>
  );
}
