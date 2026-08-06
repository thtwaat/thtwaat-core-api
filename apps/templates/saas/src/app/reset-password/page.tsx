"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { authApi } from "@/lib/services";
import { resetSchema } from "@/lib/validators";
import type { z } from "zod";

function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") || "";
  const form = useForm<z.infer<typeof resetSchema>>({
    resolver: zodResolver(resetSchema),
    defaultValues: { token, new_password: "" }
  });

  async function onSubmit(values: z.infer<typeof resetSchema>) {
    try {
      await authApi.resetPassword(values);
      toast.success("Password updated — sign in");
      router.replace("/login");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Reset failed");
    }
  }

  if (!token) {
    return (
      <AuthShell title="Reset password" subtitle="This link is missing or incomplete">
        <p className="text-sm text-muted">
          Request a new link from{" "}
          <Link className="text-brand" href="/forgot-password">Forgot password</Link>.
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password" subtitle="Use at least 8 characters">
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
        <input type="hidden" {...form.register("token")} />
        <div>
          <Label>New password</Label>
          <Input type="password" autoComplete="new-password" {...form.register("new_password")} />
        </div>
        <Button className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Updating…" : "Update password"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        <Link className="text-brand" href="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center text-sm text-muted">Loading…</div>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
