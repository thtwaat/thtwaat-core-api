"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { authApi } from "@/lib/services";
import { forgotSchema, resetSchema } from "@/lib/validators";
import type { z } from "zod";

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<"request" | "reset">("request");
  const forgot = useForm<z.infer<typeof forgotSchema>>({ resolver: zodResolver(forgotSchema) });
  const reset = useForm<z.infer<typeof resetSchema>>({ resolver: zodResolver(resetSchema) });

  async function requestReset(values: z.infer<typeof forgotSchema>) {
    try {
      await authApi.forgotPassword(values.email);
      reset.setValue("email", values.email);
      setStep("reset");
      toast.success("Reset code sent if the account exists");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start reset");
    }
  }

  async function submitReset(values: z.infer<typeof resetSchema>) {
    try {
      await authApi.resetPassword(values);
      toast.success("Password updated — sign in");
      window.location.href = "/login";
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Reset failed");
    }
  }

  return (
    <AuthShell title="Forgot password" subtitle="We'll email a 6-digit reset code">
      {step === "request" ? (
        <form className="space-y-4" onSubmit={forgot.handleSubmit(requestReset)}>
          <div>
            <Label>Email</Label>
            <Input type="email" {...forgot.register("email")} />
          </div>
          <Button className="w-full">Send reset code</Button>
        </form>
      ) : (
        <form className="space-y-4" onSubmit={reset.handleSubmit(submitReset)}>
          <div>
            <Label>Email</Label>
            <Input type="email" {...reset.register("email")} />
          </div>
          <div>
            <Label>Code</Label>
            <Input {...reset.register("code")} placeholder="123456" />
          </div>
          <div>
            <Label>New password</Label>
            <Input type="password" {...reset.register("new_password")} />
          </div>
          <Button className="w-full">Update password</Button>
        </form>
      )}
      <p className="mt-4 text-center text-sm text-muted">
        <Link className="text-brand" href="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
