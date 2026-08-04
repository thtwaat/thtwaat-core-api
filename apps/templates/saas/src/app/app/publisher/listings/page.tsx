"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { agentStoreApi, type AgentListing } from "@/lib/services";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { PublisherNav, statusBadgeClass } from "@/components/publisher/nav";

type SortKey = "updated" | "title" | "installs" | "status";

export default function PublisherListingsPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState<SortKey>("updated");

  const listings = useQuery({
    queryKey: ["publisher-listings"],
    queryFn: () => agentStoreApi.myListings()
  });

  const duplicateMut = useMutation({
    mutationFn: (id: string) => agentStoreApi.duplicateListing(id),
    onSuccess: () => {
      toast.success("Listing duplicated");
      qc.invalidateQueries({ queryKey: ["publisher-listings"] });
      qc.invalidateQueries({ queryKey: ["publisher-analytics"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const archiveMut = useMutation({
    mutationFn: (id: string) => agentStoreApi.archiveListing(id),
    onSuccess: () => {
      toast.success("Listing archived");
      qc.invalidateQueries({ queryKey: ["publisher-listings"] });
      qc.invalidateQueries({ queryKey: ["publisher-analytics"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const rows = useMemo(() => {
    let items = [...(listings.data ?? [])];
    if (status !== "all") {
      items = items.filter((l) => l.status === status);
    }
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      items = items.filter(
        (l) =>
          l.title.toLowerCase().includes(needle) ||
          l.slug.toLowerCase().includes(needle) ||
          (l.short_description || "").toLowerCase().includes(needle)
      );
    }
    items.sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title);
      if (sort === "installs") return (b.install_count || 0) - (a.install_count || 0);
      if (sort === "status") return a.status.localeCompare(b.status);
      return (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at);
    });
    return items;
  }, [listings.data, q, status, sort]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Templates"
        description="Search, filter, and manage your marketplace listings."
        action={
          <Link href="/app/publisher/listings/new" className={buttonVariants()}>
            New template
          </Link>
        }
      />
      <PublisherNav />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          placeholder="Search templates…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="sm:max-w-xs"
        />
        <select
          className="h-11 rounded-xl border border-line bg-panel px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="private">Private</option>
          <option value="pending_review">Pending</option>
          <option value="published">Published</option>
          <option value="rejected">Rejected</option>
          <option value="archived">Archived</option>
        </select>
        <select
          className="h-11 rounded-xl border border-line bg-panel px-3 text-sm"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
        >
          <option value="updated">Sort: Updated</option>
          <option value="title">Sort: Title</option>
          <option value="installs">Sort: Installs</option>
          <option value="status">Sort: Status</option>
        </select>
      </div>

      {listings.isLoading ? (
        <p className="text-sm text-muted">Loading listings…</p>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No templates yet"
          description="Create your first listing with the publish wizard."
        />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-line bg-panel">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Template</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Version</th>
                <th className="px-4 py-3 font-medium">Installs</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l: AgentListing) => (
                <tr key={l.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-ink">{l.title}</p>
                    <p className="text-xs text-muted">{l.slug}</p>
                  </td>
                  <td className="px-4 py-3">
                    <Badge className={cn("capitalize", statusBadgeClass(l.status))}>
                      {l.status.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted">v{l.current_version}</td>
                  <td className="px-4 py-3 text-muted">{l.install_count}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Link
                        href={`/app/publisher/listings/${l.id}`}
                        className={buttonVariants({ variant: "secondary", size: "sm" })}
                      >
                        Edit
                      </Link>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => duplicateMut.mutate(l.id)}
                        disabled={duplicateMut.isPending}
                      >
                        Duplicate
                      </Button>
                      {l.status !== "archived" ? (
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => {
                            if (confirm(`Archive “${l.title}”?`)) archiveMut.mutate(l.id);
                          }}
                          disabled={archiveMut.isPending}
                        >
                          Delete
                        </Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {rows.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.slice(0, 6).map((l) => (
            <Card key={`card-${l.id}`} className="space-y-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="font-semibold text-ink">{l.title}</p>
                <Badge className={cn("capitalize", statusBadgeClass(l.status))}>
                  {l.status.replace("_", " ")}
                </Badge>
              </div>
              <p className="line-clamp-2 text-sm text-muted">{l.short_description || "No description"}</p>
              <Link
                href={`/app/publisher/listings/${l.id}`}
                className="text-sm font-medium text-teal-700 hover:underline"
              >
                Open editor →
              </Link>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  );
}
