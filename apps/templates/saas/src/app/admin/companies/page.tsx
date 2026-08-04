"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { companiesApi, platformAdminApi } from "@/lib/services";
import {
  COMPANY_PLAN_OPTIONS,
  COMPANY_STATUS_OPTIONS,
  QUOTA_FIELDS,
  planLabel,
  saveAdminSessionBackup
} from "@/lib/super-admin";
import { getAccessToken, getRefreshToken, setTokens } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";

export default function AdminCompaniesPage() {
  const router = useRouter();
  const { refreshProfile } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [quotaDraft, setQuotaDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const listQ = useQuery({
    queryKey: ["admin-companies", q, status, plan],
    queryFn: () =>
      companiesApi.list({
        page: 1,
        page_size: 50,
        q: q || undefined,
        status: status || undefined,
        plan: plan || undefined,
        include_inactive: true
      })
  });

  const rows = listQ.data?.results || [];
  const selectedRow = useMemo(
    () => rows.find((r) => r.id === selected) || null,
    [rows, selected]
  );

  async function patchCompany(id: string, body: Record<string, unknown>, okMsg: string) {
    setBusy(true);
    try {
      await companiesApi.adminUpdate(id, body);
      toast.success(okMsg);
      await listQ.refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function loginAs(id: string) {
    setBusy(true);
    try {
      const access = getAccessToken();
      const refresh = getRefreshToken();
      if (access && refresh) saveAdminSessionBackup({ access_token: access, refresh_token: refresh });
      const tokens = await platformAdminApi.impersonateCompany(id, "Super Admin console");
      setTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        token_type: tokens.token_type,
        expires_in: tokens.expires_in
      });
      await refreshProfile();
      toast.success(`Logged in as ${tokens.company_name}`);
      router.push("/app");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impersonation failed");
    } finally {
      setBusy(false);
    }
  }

  async function applyQuotas() {
    if (!selected) return;
    const body: Record<string, number> = {};
    for (const field of QUOTA_FIELDS) {
      const raw = quotaDraft[field.key];
      if (raw == null || raw === "") continue;
      const n = Number(raw);
      if (!Number.isFinite(n) || n < 0) {
        toast.error(`Invalid ${field.label}`);
        return;
      }
      body[field.key] = n;
    }
    if (!Object.keys(body).length) {
      toast.message("Enter at least one quota override");
      return;
    }
    await patchCompany(selected, body, "Quotas overridden");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        description="Search, suspend/activate, change plan, override quotas, login as company."
      />

      <div className="grid gap-3 sm:grid-cols-4">
        <Input
          placeholder="Search name or slug"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search companies"
        />
        <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter status">
          <option value="">All statuses</option>
          {COMPANY_STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
        <Select value={plan} onChange={(e) => setPlan(e.target.value)} aria-label="Filter plan">
          <option value="">All plans</option>
          {COMPANY_PLAN_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
        <Button variant="secondary" onClick={() => void listQ.refetch()} disabled={listQ.isFetching}>
          Refresh
        </Button>
      </div>

      {listQ.isError && (
        <EmptyState title="Failed to load companies" description={(listQ.error as Error).message} />
      )}

      <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-line text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Active</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-line/70">
                <td className="px-4 py-3">
                  <button
                    type="button"
                    className="text-left font-medium text-ink hover:text-brand"
                    onClick={() => setSelected(row.id)}
                  >
                    {row.name}
                  </button>
                  <p className="text-xs text-muted">{row.slug}</p>
                </td>
                <td className="px-4 py-3">{planLabel(row.plan)}</td>
                <td className="px-4 py-3">
                  <Badge tone={row.status === "suspended" ? "danger" : "neutral"}>{row.status}</Badge>
                </td>
                <td className="px-4 py-3">{row.is_active ? "yes" : "no"}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy || row.status === "suspended"}
                      onClick={() =>
                        void patchCompany(row.id, { status: "suspended" }, "Company suspended")
                      }
                    >
                      Suspend
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy || row.status === "active"}
                      onClick={() =>
                        void patchCompany(
                          row.id,
                          { status: "active", is_active: true },
                          "Company activated"
                        )
                      }
                    >
                      Activate
                    </Button>
                    <Select
                      className="h-9 w-28 text-xs"
                      aria-label={`Change plan for ${row.name}`}
                      value={row.plan || "free"}
                      disabled={busy}
                      onChange={(e) =>
                        void patchCompany(row.id, { plan: e.target.value }, "Plan updated")
                      }
                    >
                      {COMPANY_PLAN_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </Select>
                    <Button size="sm" disabled={busy} onClick={() => void loginAs(row.id)}>
                      Login as
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && !listQ.isLoading && (
          <div className="p-6">
            <EmptyState title="No companies" description="Try clearing filters." />
          </div>
        )}
      </div>

      {selectedRow && (
        <Card className="space-y-4">
          <h2 className="font-semibold text-ink">Quota override — {selectedRow.name}</h2>
          <p className="text-sm text-muted">
            Writes usage meter limits via existing company admin update + UsageService.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {QUOTA_FIELDS.map((field) => (
              <div key={field.key}>
                <Label htmlFor={field.key}>{field.label}</Label>
                <Input
                  id={field.key}
                  inputMode="numeric"
                  value={quotaDraft[field.key] || ""}
                  onChange={(e) =>
                    setQuotaDraft((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
          <Button onClick={() => void applyQuotas()} disabled={busy}>
            Apply quota overrides
          </Button>
        </Card>
      )}
    </div>
  );
}
