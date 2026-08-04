"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { setTokens } from "@/lib/api";
import { onboardingApi } from "@/lib/services";
import { useAuth } from "@/lib/auth";
import { signupSchema } from "@/lib/validators";
import { clearOnboardingDraft, defaultOnboardingDraft, saveOnboardingDraft } from "@/lib/onboarding";
import type { z } from "zod";

type FormValues = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const router = useRouter();
  const { refreshProfile } = useAuth();
  const form = useForm<FormValues>({ resolver: zodResolver(signupSchema) });

  async function onSubmit(values: FormValues) {
    try {
      const started = await onboardingApi.start({
        account: {
          email: values.email,
          password: values.password,
          first_name: values.first_name,
          last_name: values.last_name
        },
        company: {
          name: values.company_name,
          slug: values.company_slug,
          display_name: values.company_name
        },
        send_verification: true
      });
      setTokens({
        access_token: started.access_token,
        refresh_token: started.refresh_token,
        token_type: started.token_type || "bearer",
        expires_in: started.expires_in
      });
      clearOnboardingDraft();
      saveOnboardingDraft({
        ...defaultOnboardingDraft(),
        displayName: values.company_name,
        uiStep: 1
      });
      await refreshProfile();
      toast.success("Welcome — let's finish setup");
      router.replace("/app/onboarding");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Signup failed");
    }
  }

  return (
    <AuthShell title="Create workspace" subtitle="Company + owner account — then guided setup">
      <form className="space-y-3" onSubmit={form.handleSubmit(onSubmit)}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label>First name</Label>
            <Input {...form.register("first_name")} />
          </div>
          <div>
            <Label>Last name</Label>
            <Input {...form.register("last_name")} />
          </div>
        </div>
        <div>
          <Label>Work email</Label>
          <Input type="email" {...form.register("email")} />
        </div>
        <div>
          <Label>Password</Label>
          <Input type="password" {...form.register("password")} />
        </div>
        <div>
          <Label>Company name</Label>
          <Input {...form.register("company_name")} />
        </div>
        <div>
          <Label>Company slug</Label>
          <Input placeholder="acme-ai" {...form.register("company_slug")} />
        </div>
        <Button className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        Already have an account? <Link className="text-brand" href="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
