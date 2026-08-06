"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { authApi } from "@/lib/services";
import { forgotSchema } from "@/lib/validators";
import type { z } from "zod";

export default function ForgotPasswordPage() {
  const forgot = useForm<z.infer<typeof forgotSchema>>({ resolver: zodResolver(forgotSchema) });

  async function requestReset(values: z.infer<typeof forgotSchema>) {
    try {
      await authApi.forgotPassword(values.email);
      toast.success("If an account exists, a reset link is on its way");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start reset");
    }
  }

  return (
    <AuthShell title="Forgot password" subtitle="We'll email a secure reset link">
      <form className="space-y-4" onSubmit={forgot.handleSubmit(requestReset)}>
        <div>
          <Label>Email</Label>
          <Input type="email" {...forgot.register("email")} />
        </div>
        <Button className="w-full">Send reset link</Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        <Link className="text-brand" href="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
