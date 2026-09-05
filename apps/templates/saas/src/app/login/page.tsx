"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { loginSchema } from "@/lib/validators";
import { authApi, onboardingApi } from "@/lib/services";
import { ApiError } from "@/lib/api";
import { isCompanyRequiredError } from "./login-helpers";
import type { z } from "zod";

type FormValues = z.infer<typeof loginSchema>;

/** Only allow same-origin app paths; block open redirects (//evil, https://…). */
function safeNextPath(raw: string | null): string {
  if (!raw) return "/app";
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.includes("://")) {
    return "/app";
  }
  if (!(raw === "/app" || raw.startsWith("/app/"))) {
    return "/app";
  }
  return raw;
}

async function postLoginDestination(preferred: string): Promise<string> {
  try {
    let session = await onboardingApi.me();
    if (session.status === "paused") {
      session = await onboardingApi.resume();
    }
    if (session.status === "in_progress") return "/app/onboarding";
  } catch (err) {
    if (!(err instanceof ApiError && (err.status === 404 || err.status === 409))) {
      /* fall through to preferred destination */
    }
  }
  return preferred === "/app" || preferred.startsWith("/app/") ? preferred : "/app";
}

function LoginForm() {
  const { login, completeMfa } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [totp, setTotp] = useState("");
  const [companyRequired, setCompanyRequired] = useState(false);
  const [companyMessage, setCompanyMessage] = useState<string | null>(null);
  const form = useForm<FormValues>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: FormValues) {
    try {
      const result = await login(values.email, values.password, values.company_slug || undefined);
      if ("mfa_required" in result && result.mfa_required) {
        setMfaToken(result.mfa_token);
        toast.message("Enter your MFA code to continue");
        return;
      }
      toast.success("Welcome back");
      const dest = await postLoginDestination(safeNextPath(params.get("next")));
      router.replace(dest);
    } catch (error) {
      if (isCompanyRequiredError(error)) {
        setCompanyRequired(true);
        setCompanyMessage(
          error instanceof Error
            ? error.message
            : "This email belongs to multiple organizations. Enter your company slug to continue."
        );
        toast.error("Multiple organizations found — enter your company slug");
        return;
      }
      toast.error(error instanceof Error ? error.message : "Login failed");
    }
  }

  async function onMfa() {
    if (!mfaToken) return;
    try {
      await completeMfa(mfaToken, totp);
      toast.success("MFA verified");
      const dest = await postLoginDestination(safeNextPath(params.get("next")));
      router.replace(dest);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Invalid MFA code");
    }
  }

  function continueWithGoogle() {
    window.location.href = authApi.googleStartUrl();
  }

  return (
    <AuthShell title="Sign in" subtitle="Access your AI workspace">
      {!mfaToken ? (
        <div className="space-y-4">
          <Button className="w-full" type="button" onClick={continueWithGoogle}>
            Continue with Google
          </Button>
          <div className="relative py-1 text-center text-xs text-muted">
            <span className="bg-surface relative z-10 px-2">or use email</span>
            <span className="absolute inset-x-0 top-1/2 border-t border-line" />
          </div>
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...form.register("email")} />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" {...form.register("password")} />
            </div>
            {companyRequired && (
              <div>
                <Label htmlFor="company_slug">Company slug</Label>
                <Input
                  id="company_slug"
                  type="text"
                  placeholder="acme"
                  autoFocus
                  {...form.register("company_slug")}
                />
                <p className="mt-1 text-xs text-muted">
                  {companyMessage ?? "This email belongs to multiple organizations. Enter your company slug to continue."}
                </p>
              </div>
            )}
            <Button className="w-full" variant="secondary" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Signing in…" : "Sign in with email"}
            </Button>
          </form>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <Label htmlFor="totp">MFA / recovery code</Label>
            <Input id="totp" value={totp} onChange={(e) => setTotp(e.target.value)} placeholder="123456" />
          </div>
          <Button className="w-full" onClick={onMfa}>Verify MFA</Button>
        </div>
      )}
      <div className="mt-5 space-y-2 text-center text-sm text-muted">
        <p>
          <Link className="text-brand" href="/forgot-password">Forgot password?</Link>
        </p>
        <p>
          Need an account? <Link className="text-brand" href="/signup">Sign up</Link>
        </p>
      </div>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center text-sm text-muted">Loading…</div>}>
      <LoginForm />
    </Suspense>
  );
}
