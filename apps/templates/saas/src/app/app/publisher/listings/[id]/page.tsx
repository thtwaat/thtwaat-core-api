"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { agentStoreApi } from "@/lib/services";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/card";
import { PublisherNav, statusBadgeClass } from "@/components/publisher/nav";
import { cn } from "@/lib/utils";

export default function EditListingPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const qc = useQueryClient();

  const listings = useQuery({
    queryKey: ["publisher-listings"],
    queryFn: () => agentStoreApi.myListings()
  });
  const listing = (listings.data ?? []).find((l) => l.id === id);

  const [title, setTitle] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [longDescription, setLongDescription] = useState("");
  const [demoUrl, setDemoUrl] = useState("");
  const [coverUrl, setCoverUrl] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [tags, setTags] = useState("");

  useEffect(() => {
    if (!listing) return;
    setTitle(listing.title);
    setShortDescription(listing.short_description || "");
    setLongDescription(listing.long_description || "");
    setDemoUrl(listing.demo_url || "");
    setCoverUrl(listing.cover_url || "");
    setLogoUrl(listing.logo_url || "");
    setTags((listing.tags || []).join(", "));
  }, [listing]);

  const saveMut = useMutation({
    mutationFn: () =>
      agentStoreApi.updateListing(id, {
        title,
        short_description: shortDescription,
        long_description: longDescription,
        demo_url: demoUrl || null,
        cover_url: coverUrl || null,
        logo_url: logoUrl || null,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      }),
    onSuccess: () => {
      toast.success("Listing updated");
      qc.invalidateQueries({ queryKey: ["publisher-listings"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const submitMut = useMutation({
    mutationFn: () => agentStoreApi.submitListing(id),
    onSuccess: () => {
      toast.success("Submitted for review");
      qc.invalidateQueries({ queryKey: ["publisher-listings"] });
      qc.invalidateQueries({ queryKey: ["publisher-analytics"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const statusMut = useMutation({
    mutationFn: (status: string) => agentStoreApi.setListingStatus(id, status),
    onSuccess: () => {
      toast.success("Status updated");
      qc.invalidateQueries({ queryKey: ["publisher-listings"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  if (listings.isLoading) {
    return <p className="text-sm text-muted">Loading…</p>;
  }
  if (!listing) {
    return (
      <div className="space-y-4">
        <EmptyState title="Listing not found" />
        <Button variant="secondary" onClick={() => router.push("/app/publisher/listings")}>
          Back to listings
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={listing.title}
        description={`Edit listing · ${listing.slug}`}
        action={
          <Badge className={cn("capitalize", statusBadgeClass(listing.status))}>
            {listing.status.replace("_", " ")}
          </Badge>
        }
      />
      <PublisherNav />

      <Card className="grid gap-4 p-6 md:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">Title</span>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className="space-y-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">Demo URL</span>
          <Input value={demoUrl} onChange={(e) => setDemoUrl(e.target.value)} />
        </label>
        <label className="space-y-1.5 md:col-span-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            Short description
          </span>
          <Input value={shortDescription} onChange={(e) => setShortDescription(e.target.value)} />
        </label>
        <label className="space-y-1.5 md:col-span-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            Long description
          </span>
          <textarea
            className="min-h-28 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
            value={longDescription}
            onChange={(e) => setLongDescription(e.target.value)}
          />
        </label>
        <label className="space-y-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">Logo URL</span>
          <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} />
        </label>
        <label className="space-y-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">Cover URL</span>
          <Input value={coverUrl} onChange={(e) => setCoverUrl(e.target.value)} />
        </label>
        <label className="space-y-1.5 md:col-span-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">Tags</span>
          <Input value={tags} onChange={(e) => setTags(e.target.value)} />
        </label>

        <div className="md:col-span-2 flex flex-wrap gap-2 border-t border-line pt-4">
          <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
            Save changes
          </Button>
          {["draft", "private", "rejected"].includes(listing.status) ? (
            <Button
              variant="secondary"
              onClick={() => submitMut.mutate()}
              disabled={submitMut.isPending}
            >
              Submit for review
            </Button>
          ) : null}
          {listing.status === "draft" ? (
            <Button
              variant="ghost"
              onClick={() => statusMut.mutate("private")}
              disabled={statusMut.isPending}
            >
              Make private
            </Button>
          ) : null}
          {listing.status === "private" ? (
            <Button
              variant="ghost"
              onClick={() => statusMut.mutate("draft")}
              disabled={statusMut.isPending}
            >
              Move to draft
            </Button>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
