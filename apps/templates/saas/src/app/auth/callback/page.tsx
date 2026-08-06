"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setTokens } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { onboardingApi } from "@/lib/services";
import { ApiError } from "@/lib/api";

function parseHashTokens(): {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
} | null {
  if (typeof window === "undefined") return null;
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) return null;
  const params = new URLSearchParams(raw);
  const access_token = params.get("access_token") || undefined;
  const refresh_token = params.get("refresh_token") || undefined;
  if (!access_token || !refresh_token) return null;
  return {
    access_token,
    refresh_token,
    expires_in: Number(params.get("expires_in") || 0) || 1800,
    token_type: params.get("token_type") || "bearer"
  };
}

function AuthCallbackInner() {
  const router = useRouter();
  const { refreshProfile } = useAuth();
  const [message, setMessage] = useState("Signing you in…");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tokens = parseHashTokens();
      if (!tokens?.access_token || !tokens.refresh_token) {
        setMessage("Sign-in failed. Try again.");
        router.replace("/login?error=google_failed");
        return;
      }
      setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        token_type: tokens.token_type || "bearer",
        expires_in: tokens.expires_in || 1800
      });
      window.history.replaceState(null, "", "/auth/callback");
      try {
        await refreshProfile();
        let dest = "/app";
        try {
          let session = await onboardingApi.me();
          if (session.status === "paused") {
            session = await onboardingApi.resume();
          }
          if (session.status === "in_progress") dest = "/app/onboarding";
        } catch (err) {
          if (!(err instanceof ApiError && (err.status === 404 || err.status === 409))) {
            /* dashboard */
          }
        }
        if (!cancelled) router.replace(dest);
      } catch {
        if (!cancelled) {
          setMessage("Could not load your profile");
          router.replace("/login?error=google_failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshProfile, router]);

  return (
    <div className="grid min-h-screen place-items-center text-sm text-muted">{message}</div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center text-sm text-muted">Loading…</div>}>
      <AuthCallbackInner />
    </Suspense>
  );
}
