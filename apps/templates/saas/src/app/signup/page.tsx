"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { companiesApi, usersApi } from "@/lib/services";
import { useAuth } from "@/lib/auth";
import { signupSchema } from "@/lib/validators";
import type { z } from "zod";

type FormValues = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const router = useRouter();
  const { login } = useAuth();
  const form = useForm<FormValues>({ resolver: zodResolver(signupSchema) });

  async function onSubmit(values: FormValues) {
    try {
      const company = await companiesApi.create({
        name: values.company_name,
        slug: values.company_slug
      });
      await usersApi.create({
        email: values.email,
        password: values.password,
        first_name: values.first_name,
        last_name: values.last_name,
        company_id: company.id,
        role: "company_owner"
      });
      await login(values.email, values.password);
      toast.success("Workspace created");
      router.replace("/app");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Signup failed");
    }
  }

  return (
    <AuthShell title="Create workspace" subtitle="Company + owner account in one step">
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
