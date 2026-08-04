"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { usersApi } from "@/lib/services";
import { USER_ROLE_OPTIONS } from "@/lib/super-admin";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";

export default function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);

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

  return (
    <div className="space-y-6">
      <PageHeader title="Users" description="Search users, change roles, enable or disable accounts." />

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
                    {active ? (
                      <Button size="sm" variant="secondary" disabled={busy} onClick={() => void setActive(id, false)}>
                        Disable
                      </Button>
                    ) : (
                      <Button size="sm" disabled={busy} onClick={() => void setActive(id, true)}>
                        Enable
                      </Button>
                    )}
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
