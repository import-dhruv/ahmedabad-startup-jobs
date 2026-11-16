"use client";

import * as React from "react";

import { authApi, type User } from "@/lib/api";

const STORAGE_KEY = "ahsj-session";

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [token, setToken] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      setLoading(false);
      return;
    }
    try {
      const parsed = JSON.parse(raw) as { token: string; user: User };
      setToken(parsed.token);
      setUser(parsed.user);
      authApi
        .me(parsed.token)
        .then((fresh) => {
          setUser(fresh);
          localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: parsed.token, user: fresh }));
        })
        .catch(() => {
          localStorage.removeItem(STORAGE_KEY);
          setToken(null);
          setUser(null);
        })
        .finally(() => setLoading(false));
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      setLoading(false);
    }
  }, []);

  const persist = React.useCallback((nextToken: string, nextUser: User) => {
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: nextToken, user: nextUser }));
  }, []);

  const value = React.useMemo<AuthState>(
    () => ({
      user,
      token,
      loading,
      async login(email, password) {
        const res = await authApi.login({ email, password });
        persist(res.access_token, res.user);
      },
      async register(email, password, fullName) {
        const res = await authApi.register({ email, password, full_name: fullName });
        persist(res.access_token, res.user);
      },
      async loginWithGoogle(idToken) {
        const res = await authApi.googleSignIn(idToken);
        persist(res.access_token, res.user);
      },
      logout() {
        localStorage.removeItem(STORAGE_KEY);
        setToken(null);
        setUser(null);
      },
    }),
    [user, token, loading, persist],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
