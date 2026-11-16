"use client";

import * as React from "react";

import { authApi, type User } from "@/lib/api";

const STORAGE_KEY = "ahsj-session";

interface Session {
  token: string;
  user: User;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = React.createContext<AuthState | null>(null);

/**
 * The session lives in localStorage, so it is read through
 * `useSyncExternalStore` instead of being copied into state inside an effect.
 * The stored user is refreshed from the API in the background.
 */
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

// useSyncExternalStore requires getSnapshot to return the same value until the
// store actually changes. Parse only when the raw localStorage value changes,
// otherwise React sees a new object on every read and re-renders forever.
let cachedRaw: string | null | undefined;
let cachedSession: Session | null = null;

function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    if (!raw) {
      cachedSession = null;
    } else {
      try {
        const parsed = JSON.parse(raw) as Session;
        cachedSession = parsed?.token ? parsed : null;
      } catch {
        cachedSession = null;
      }
    }
  }
  return cachedSession;
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function writeSession(session: Session | null) {
  if (session) {
    const raw = JSON.stringify(session);
    window.localStorage.setItem(STORAGE_KEY, raw);
    cachedRaw = raw;
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
    cachedRaw = null;
  }
  cachedSession = session;
  notify();
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const session = React.useSyncExternalStore(subscribe, readSession, () => null);
  const token = session?.token ?? null;

  // Keep the stored user fresh. The session itself is never mirrored into
  // state, so this only reconciles data, it does not drive rendering.
  React.useEffect(() => {
    if (!token) return;
    let cancelled = false;
    authApi
      .me(token)
      .then((fresh) => {
        if (cancelled) return;
        const current = readSession();
        if (current) writeSession({ token: current.token, user: fresh });
      })
      .catch(() => {
        if (!cancelled) writeSession(null);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const value = React.useMemo<AuthState>(
    () => ({
      user: session?.user ?? null,
      token,
      loading: false,
      async login(email, password) {
        const res = await authApi.login({ email, password });
        writeSession({ token: res.access_token, user: res.user });
      },
      async register(email, password, fullName) {
        const res = await authApi.register({ email, password, full_name: fullName });
        writeSession({ token: res.access_token, user: res.user });
      },
      async loginWithGoogle(idToken) {
        const res = await authApi.googleSignIn(idToken);
        writeSession({ token: res.access_token, user: res.user });
      },
      logout() {
        writeSession(null);
      },
    }),
    [session, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
