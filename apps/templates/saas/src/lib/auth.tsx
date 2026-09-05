"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import { api, clearTokens, getAccessToken, setTokens } from "@/lib/api";
import type { MfaChallenge, TokenPair, UserProfile } from "@/lib/types";

type AuthContextValue = {
  user: UserProfile | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string, companySlug?: string) => Promise<TokenPair | MfaChallenge>;
  completeMfa: (mfaToken: string, totp: string) => Promise<TokenPair>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshProfile = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      return;
    }
    const profile = await api.v1<UserProfile>("/auth/me");
    setUser(profile);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        if (getAccessToken()) await refreshProfile();
      } catch {
        clearTokens();
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshProfile]);

  const login = useCallback(async (email: string, password: string, companySlug?: string) => {
    const result = await api.v1<TokenPair | MfaChallenge>("/auth/login", {
      method: "POST",
      auth: false,
      body: companySlug ? { email, password, company_slug: companySlug } : { email, password }
    });
    if ("mfa_required" in result && result.mfa_required) return result;
    setTokens(result as TokenPair);
    await refreshProfile();
    return result;
  }, [refreshProfile]);

  const completeMfa = useCallback(
    async (mfaToken: string, totp: string) => {
      const tokens = await api.v1<TokenPair>("/auth/mfa/verify", {
        method: "POST",
        auth: false,
        body: { mfa_token: mfaToken, totp }
      });
      setTokens(tokens);
      await refreshProfile();
      return tokens;
    },
    [refreshProfile]
  );

  const logout = useCallback(async () => {
    try {
      const refresh = typeof window !== "undefined" ? window.localStorage.getItem("tht_refresh_token") : null;
      if (refresh) {
        await api.v1("/auth/logout", { method: "POST", auth: false, body: { refresh_token: refresh } });
      }
    } catch {
      // ignore logout network errors
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      completeMfa,
      logout,
      refreshProfile
    }),
    [user, loading, login, completeMfa, logout, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
