"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { authApi } from "@/lib/services";
import { otpSchema } from "@/lib/validators";
import type { z } from "zod";

type FormValues = z.infer<typeof otpSchema>;

export default function OtpPage() {
  const form = useForm<FormValues>({
    resolver: zodResolver(otpSchema),
    defaultValues: { purpose: "LOGIN" }
  });

  async function sendCode() {
    const email = form.getValues("email");
    const purpose = form.getValues("purpose");
    if (!email) return toast.error("Enter email first");
    try {
      await authApi.sendOtp({ email, purpose });
      toast.success("OTP sent");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not send OTP");
    }
  }

  async function verify(values: FormValues) {
    try {
      await authApi.verifyOtp(values);
      toast.success("OTP verified");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Invalid OTP");
    }
  }

  return (
    <AuthShell title="OTP verification" subtitle="Works with backend OTP purposes">
      <form className="space-y-4" onSubmit={form.handleSubmit(verify)}>
        <div>
          <Label>Email</Label>
          <Input type="email" {...form.register("email")} />
        </div>
        <div>
          <Label>Purpose</Label>
          <Select {...form.register("purpose")}>
            <option value="LOGIN">LOGIN</option>
            <option value="REGISTER">REGISTER</option>
            <option value="PASSWORD_RESET">PASSWORD_RESET</option>
            <option value="EMAIL_VERIFY">EMAIL_VERIFY</option>
            <option value="MFA">MFA</option>
          </Select>
        </div>
        <div>
          <Label>Code</Label>
          <Input {...form.register("code")} placeholder="123456" />
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <Button type="button" variant="secondary" onClick={sendCode}>Send OTP</Button>
          <Button type="submit">Verify</Button>
        </div>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        <Link className="text-brand" href="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
