"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { platformAdminApi } from "@/lib/services";
import { LOG_CATEGORIES, downloadAdminExport } from "@/lib/super-admin";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";

export default function AdminAuditLogsPage() {
  const [category, setCategory] = useState("all");
  const q = useQuery({
    queryKey: ["admin-logs", category],
    queryFn: () => platformAdminApi.logs(category, 100)
  });

  const items = q.data?.items || [];

  async function doExport(format: "csv" | "xlsx" | "pdf") {
    try {
      const payload = await platformAdminApi.export("logs", format);
      downloadAdminExport(payload);
      toast.success(`Exported ${payload.filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations Logs"
        description="Unified audit, payment, webhook, authentication, and AI logs."
        action={
          <div className="flex flex-wrap gap-2">
            <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Log category">
              {LOG_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
            <Button variant="secondary" onClick={() => void q.refetch()}>
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => void doExport("csv")}>
              CSV
            </Button>
            <Button variant="secondary" onClick={() => void doExport("pdf")}>
              PDF
            </Button>
          </div>
        }
      />

      {q.isError && <EmptyState title="Failed to load logs" description={(q.error as Error).message} />}

      <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-line text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Resource</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row, idx) => (
              <tr key={`${String(row.resource_id)}-${idx}`} className="border-b border-line/70 align-top">
                <td className="px-4 py-3 text-xs text-muted">{String(row.created_at || "—")}</td>
                <td className="px-4 py-3">
                  <Badge tone="neutral">{String(row.category)}</Badge>
                </td>
                <td className="px-4 py-3">{String(row.action || "—")}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {String(row.resource_type || "")}:{String(row.resource_id || "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && !q.isLoading && (
          <div className="p-6">
            <EmptyState title="No log events" description="Try another category or generate platform activity." />
          </div>
        )}
      </div>
    </div>
  );
}
