"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { ApiError, setTokens } from "@/lib/api";
import { authApi, onboardingApi } from "@/lib/services";
import { useAuth } from "@/lib/auth";
import { signupSchema } from "@/lib/validators";
import { clearOnboardingDraft, defaultOnboardingDraft, saveOnboardingDraft } from "@/lib/onboarding";
import type { z } from "zod";

type FormValues = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const router = useRouter();
  const { refreshProfile } = useAuth();
  const form = useForm<FormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      company_name: ""
    }
  });

  async function onSubmit(values: FormValues) {
    try {
      const started = await onboardingApi.start({
        account: {
          email: values.email,
          password: values.password,
          first_name: values.first_name?.trim() || "Owner",
          last_name: values.last_name?.trim() || "User"
        },
        company: {
          name: values.company_name.trim(),
          display_name: values.company_name.trim()
        },
        send_welcome_email: true
      });
      if (!started?.access_token || !started?.refresh_token) {
        toast.error("Unable to create workspace.");
        return;
      }
      setTokens({
        access_token: started.access_token,
        refresh_token: started.refresh_token,
        token_type: started.token_type || "bearer",
        expires_in: started.expires_in
      });
      clearOnboardingDraft();
      saveOnboardingDraft({
        ...defaultOnboardingDraft(),
        displayName: values.company_name.trim(),
        uiStep: 1
      });
      await refreshProfile();
      toast.success("Welcome — let's finish setup");
      router.replace("/app/onboarding");
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Unable to create workspace.";
      toast.error(message || "Unable to create workspace.");
    }
  }

  function continueWithGoogle() {
    window.location.href = authApi.googleStartUrl();
  }

  const errors = form.formState.errors;

  return (
    <AuthShell title="Create workspace" subtitle="Company + owner account — then guided setup">
      <div className="space-y-4">
        <Button className="w-full" type="button" onClick={continueWithGoogle}>
          Continue with Google
        </Button>
        <div className="relative py-1 text-center text-xs text-muted">
          <span className="bg-surface relative z-10 px-2">or create with email</span>
          <span className="absolute inset-x-0 top-1/2 border-t border-line" />
        </div>
        <form className="space-y-3" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>First name</Label>
              <Input {...form.register("first_name")} autoComplete="given-name" />
            </div>
            <div>
              <Label>Last name</Label>
              <Input {...form.register("last_name")} autoComplete="family-name" />
            </div>
          </div>
          <div>
            <Label>Work email</Label>
            <Input type="email" autoComplete="email" {...form.register("email")} />
            {errors.email ? (
              <p className="mt-1 text-xs text-rose-600">{errors.email.message}</p>
            ) : null}
          </div>
          <div>
            <Label>Password</Label>
            <Input type="password" autoComplete="new-password" {...form.register("password")} />
            {errors.password ? (
              <p className="mt-1 text-xs text-rose-600">{errors.password.message}</p>
            ) : null}
          </div>
          <div>
            <Label>Company name</Label>
            <Input {...form.register("company_name")} autoComplete="organization" />
            {errors.company_name ? (
              <p className="mt-1 text-xs text-rose-600">{errors.company_name.message}</p>
            ) : null}
          </div>
          <Button className="w-full" variant="secondary" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Creating…" : "Create account"}
          </Button>
        </form>
      </div>
      <p className="mt-4 text-center text-sm text-muted">
        Already have an account? <Link className="text-brand" href="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
