"use client";

import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { agentStoreApi, platformAdminApi } from "@/lib/services";
import { formatRevenue } from "@/lib/super-admin";
import { PageHeader, EmptyState, Stat } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function AdminMarketplacePage() {
  const analyticsQ = useQuery({
    queryKey: ["admin-marketplace-analytics"],
    queryFn: () => platformAdminApi.marketplaceAnalytics(30)
  });
  const pendingQ = useQuery({
    queryKey: ["admin-store-pending"],
    queryFn: () => agentStoreApi.pending(30)
  });
  const statsQ = useQuery({
    queryKey: ["admin-store-stats"],
    queryFn: () => agentStoreApi.adminStats()
  });

  const catalog = (analyticsQ.data?.catalog as Record<string, unknown>) || {};
  const store = (analyticsQ.data?.store as Record<string, unknown>) || (statsQ.data as unknown as Record<string, unknown>) || {};
  const top = (catalog.top_templates as Array<Record<string, unknown>>) || [];
  const pending = pendingQ.data || [];

  async function moderate(id: string, action: string) {
    try {
      await agentStoreApi.moderate(id, { action });
      toast.success(`${action} applied`);
      await pendingQ.refetch();
      await statsQ.refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Moderation failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Marketplace & Publishers"
        description="Catalog analytics, publisher moderation, installs and revenue."
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void analyticsQ.refetch();
              void pendingQ.refetch();
              void statsQ.refetch();
            }}
          >
            Refresh
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Published templates" value={String(catalog.published ?? "—")} />
        <Stat label="Active installs" value={String(catalog.active_installs ?? "—")} />
        <Stat label="Store listings" value={String(store.listings_total ?? "—")} />
        <Stat label="Pending review" value={String(store.pending_review ?? "—")} />
        <Stat label="Store GMV" value={formatRevenue(Number(store.gross_gmv ?? 0))} />
        <Stat label="Suspended" value={String(store.suspended ?? "—")} />
        <Stat label="Abuse open" value={String(store.open_abuse_reports ?? "—")} />
        <Stat label="Purchases" value={String(store.purchases_completed ?? "—")} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Most installed</h2>
          <ul className="max-h-80 space-y-2 overflow-auto text-sm">
            {top.map((t) => (
              <li key={String(t.template_id || t.slug)} className="flex justify-between gap-3 border-b border-line/50 py-1">
                <span>{String(t.name)}</span>
                <span className="text-muted">{String(t.install_count)}</span>
              </li>
            ))}
            {!top.length && <li className="text-muted">No catalog ranks yet.</li>}
          </ul>
        </Card>

        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Publisher moderation queue</h2>
          <ul className="max-h-80 space-y-3 overflow-auto text-sm">
            {pending.map((listing) => (
              <li key={listing.id} className="space-y-2 border-b border-line/50 pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-ink">{listing.title || listing.slug}</p>
                    <p className="text-xs text-muted">{listing.status}</p>
                  </div>
                  <Badge tone="warn">pending</Badge>
                </div>
                <div className="flex flex-wrap gap-1">
                  {["approve", "reject", "verify", "feature", "suspend"].map((action) => (
                    <Button
                      key={action}
                      size="sm"
                      variant="secondary"
                      onClick={() => void moderate(listing.id, action)}
                    >
                      {action}
                    </Button>
                  ))}
                </div>
              </li>
            ))}
            {!pending.length && <li className="text-muted">No pending listings.</li>}
          </ul>
        </Card>
      </div>

      {(analyticsQ.isError || pendingQ.isError) && (
        <EmptyState
          title="Partial marketplace load failure"
          description={(analyticsQ.error as Error)?.message || (pendingQ.error as Error)?.message}
        />
      )}
    </div>
  );
}
