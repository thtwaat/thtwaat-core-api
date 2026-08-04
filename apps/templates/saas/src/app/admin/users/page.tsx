"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { platformAdminApi, usersApi } from "@/lib/services";
import { USER_ROLE_OPTIONS } from "@/lib/super-admin";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";

export default function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteCompanyId, setInviteCompanyId] = useState("");
  const [inviteRole, setInviteRole] = useState("employee");
  const [tempSecret, setTempSecret] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["admin-users", q, role],
    queryFn: () =>
      usersApi.listPage({
        page: 1,
        page_size: 50,
        q: q || undefined,
        role: role || undefined,
        include_inactive: true
      })
  });

  const rows = listQ.data?.results || [];

  async function setActive(id: string, is_active: boolean) {
    setBusy(true);
    try {
      if (!is_active) {
        await usersApi.deactivate(id);
      } else {
        await usersApi.update(id, { is_active: true, status: "active" });
      }
      toast.success(is_active ? "User enabled" : "User disabled");
      await listQ.refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function changeRole(id: string, nextRole: string) {
    setBusy(true);
    try {
      await usersApi.update(id, { role: nextRole });
      toast.success("Role updated");
      await listQ.refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Role update failed");
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(id: string) {
    setBusy(true);
    try {
      const res = await platformAdminApi.resetPassword(id);
      setTempSecret(res.temporary_password);
      toast.success(`Temporary password issued for ${res.email}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  }

  async function inviteUser() {
    if (!inviteEmail || !inviteCompanyId) {
      toast.error("Email and company id are required");
      return;
    }
    setBusy(true);
    try {
      const res = await platformAdminApi.inviteUser({
        email: inviteEmail,
        company_id: inviteCompanyId,
        role: inviteRole
      });
      setTempSecret(res.temporary_password);
      toast.success(`Invited ${inviteEmail}`);
      setInviteEmail("");
      await listQ.refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Search users, invite, change roles, disable accounts, reset passwords."
      />

      <Card className="grid gap-3 sm:grid-cols-4">
        <div>
          <Label htmlFor="invite-email">Invite email</Label>
          <Input
            id="invite-email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="user@company.com"
          />
        </div>
        <div>
          <Label htmlFor="invite-company">Company ID</Label>
          <Input
            id="invite-company"
            value={inviteCompanyId}
            onChange={(e) => setInviteCompanyId(e.target.value)}
            placeholder="uuid"
          />
        </div>
        <div>
          <Label htmlFor="invite-role">Role</Label>
          <Select
            id="invite-role"
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
          >
            {USER_ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex items-end">
          <Button className="w-full" disabled={busy} onClick={() => void inviteUser()}>
            Invite user
          </Button>
        </div>
        {tempSecret && (
          <p className="sm:col-span-4 rounded-xl bg-canvas p-3 text-sm">
            Temporary password (copy now): <span className="font-mono">{tempSecret}</span>
          </p>
        )}
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <Input
          placeholder="Search email or name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search users"
        />
        <Select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Filter role">
          <option value="">All roles</option>
          {USER_ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
        <Button variant="secondary" onClick={() => void listQ.refetch()}>
          Refresh
        </Button>
      </div>

      {listQ.isError && (
        <EmptyState title="Failed to load users" description={(listQ.error as Error).message} />
      )}

      <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-line text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const id = String(row.id);
              const active = Boolean(row.is_active);
              return (
                <tr key={id} className="border-b border-line/70">
                  <td className="px-4 py-3">
                    <p className="font-medium text-ink">
                      {String(row.first_name || "")} {String(row.last_name || "")}
                    </p>
                    <p className="text-xs text-muted">{String(row.email)}</p>
                  </td>
                  <td className="px-4 py-3">
                    <Select
                      className="h-9 text-xs"
                      value={String(row.role || "employee")}
                      disabled={busy}
                      aria-label={`Role for ${row.email}`}
                      onChange={(e) => void changeRole(id, e.target.value)}
                    >
                      {USER_ROLE_OPTIONS.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={active ? "success" : "danger"}>
                      {active ? String(row.status || "active") : "disabled"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {active ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busy}
                          onClick={() => void setActive(id, false)}
                        >
                          Disable
                        </Button>
                      ) : (
                        <Button size="sm" disabled={busy} onClick={() => void setActive(id, true)}>
                          Enable
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={busy}
                        onClick={() => void resetPassword(id)}
                      >
                        Reset password
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!rows.length && !listQ.isLoading && (
          <div className="p-6">
            <EmptyState title="No users" description="Try clearing search filters." />
          </div>
        )}
      </div>
    </div>
  );
}
