"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { apiKeysApi, companiesApi, usersApi } from "@/lib/services";
import { companySchema, profileSchema } from "@/lib/validators";
import { PageHeader } from "@/components/ui/misc";
import { Card, CardHeader, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import type { z } from "zod";

export default function SettingsPage() {
  const { user, refreshProfile } = useAuth();
  const qc = useQueryClient();
  const [theme, setTheme] = useState("system");
  const [brand, setBrand] = useState("#0f766e");

  const members = useQuery({ queryKey: ["users"], queryFn: usersApi.list });
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list });
  const company = useQuery({
    queryKey: ["company", user?.company_id],
    queryFn: () => companiesApi.get(user!.company_id),
    enabled: Boolean(user?.company_id)
  });

  const profileForm = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema)
  });
  const companyForm = useForm<z.infer<typeof companySchema>>({
    resolver: zodResolver(companySchema)
  });

  useEffect(() => {
    if (user) {
      profileForm.reset({
        first_name: user.first_name,
        last_name: user.last_name,
        email: user.email
      });
    }
  }, [user, profileForm]);

  useEffect(() => {
    if (company.data) {
      companyForm.reset({
        name: company.data.name,
        brand_color: company.data.brand_color || "#0f766e",
        logo_url: company.data.logo_url || ""
      });
      if (company.data.brand_color) setBrand(company.data.brand_color);
    }
  }, [company.data, companyForm]);

  const saveProfile = useMutation({
    mutationFn: (values: z.infer<typeof profileSchema>) => usersApi.update(user!.id, values),
    onSuccess: async () => {
      toast.success("Profile updated");
      await refreshProfile();
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const saveCompany = useMutation({
    mutationFn: (values: z.infer<typeof companySchema>) =>
      companiesApi.update(user!.company_id, { ...values, brand_color: brand }),
    onSuccess: () => {
      toast.success("Company updated");
      qc.invalidateQueries({ queryKey: ["company", user?.company_id] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const createKey = useMutation({
    mutationFn: () => apiKeysApi.create({ name: "Dashboard key" }),
    onSuccess: () => {
      toast.success("API key created");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const deleteKey = useMutation({
    mutationFn: (id: string) => apiKeysApi.remove(id),
    onSuccess: () => {
      toast.success("API key deleted");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Profile, company, brand, theme, members, and API keys." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Profile" />
          <form className="space-y-3" onSubmit={profileForm.handleSubmit((v) => saveProfile.mutate(v))}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label>First name</Label>
                <Input {...profileForm.register("first_name")} />
              </div>
              <div>
                <Label>Last name</Label>
                <Input {...profileForm.register("last_name")} />
              </div>
            </div>
            <div>
              <Label>Email</Label>
              <Input type="email" {...profileForm.register("email")} />
            </div>
            <Button type="submit">Save profile</Button>
          </form>
        </Card>

        <Card>
          <CardHeader title="Company & brand" />
          <form className="space-y-3" onSubmit={companyForm.handleSubmit((v) => saveCompany.mutate(v))}>
            <div>
              <Label>Company name</Label>
              <Input {...companyForm.register("name")} />
            </div>
            <div>
              <Label>Brand color</Label>
              <div className="flex gap-2">
                <Input type="color" className="w-16 p-1" value={brand} onChange={(e) => setBrand(e.target.value)} />
                <Input value={brand} onChange={(e) => setBrand(e.target.value)} />
              </div>
            </div>
            <div>
              <Label>Logo URL</Label>
              <Input {...companyForm.register("logo_url")} placeholder="https://…" />
            </div>
            <Button type="submit">Save company</Button>
          </form>
        </Card>

        <Card>
          <CardHeader title="Theme" description="Local preference for this starter UI" />
          <div className="flex flex-wrap gap-2">
            {["system", "light", "dark"].map((t) => (
              <Button key={t} variant={theme === t ? "default" : "secondary"} size="sm" onClick={() => setTheme(t)}>
                {t}
              </Button>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted">Selected: {theme}</p>
        </Card>

        <Card>
          <CardHeader
            title="Platform API keys"
            action={<Button size="sm" onClick={() => createKey.mutate()}>Create</Button>}
          />
          <div className="space-y-2">
            {(keys.data || []).map((key) => (
              <div key={String(key.id)} className="flex items-center justify-between rounded-xl border border-line px-3 py-2 text-sm">
                <div>
                  <p className="font-medium">{String(key.name || key.prefix || key.id)}</p>
                  <p className="text-xs text-muted">{key.is_active === false ? "disabled" : "active"}</p>
                </div>
                <Button size="sm" variant="danger" onClick={() => deleteKey.mutate(String(key.id))}>
                  Delete
                </Button>
              </div>
            ))}
            {!keys.data?.length && <p className="text-sm text-muted">No platform API keys.</p>}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Members" />
        <div className="space-y-2">
          {(members.data || []).map((member) => (
            <div key={String(member.id)} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm">
              <div>
                <p className="font-medium">
                  {String(member.first_name || "")} {String(member.last_name || "")}
                </p>
                <p className="text-xs text-muted">{String(member.email || "")}</p>
              </div>
              <Badge>{String(member.role || "member")}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
