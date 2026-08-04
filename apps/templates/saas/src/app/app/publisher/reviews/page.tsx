"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { agentStoreApi } from "@/lib/services";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PublisherNav } from "@/components/publisher/nav";

export default function PublisherReviewsPage() {
  const qc = useQueryClient();
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});

  const reviews = useQuery({
    queryKey: ["publisher-reviews"],
    queryFn: () => agentStoreApi.reviews()
  });

  const replyMut = useMutation({
    mutationFn: ({ id, reply }: { id: string; reply: string }) =>
      agentStoreApi.replyReview(id, reply),
    onSuccess: () => {
      toast.success("Reply posted");
      qc.invalidateQueries({ queryKey: ["publisher-reviews"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const helpfulMut = useMutation({
    mutationFn: (id: string) => agentStoreApi.markReviewHelpful(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["publisher-reviews"] }),
    onError: (e: Error) => toast.error(e.message)
  });

  const reportMut = useMutation({
    mutationFn: (listingId: string) =>
      agentStoreApi.reportAbuse(listingId, {
        reason: "abuse",
        details: "Publisher reported review content for moderation"
      }),
    onSuccess: () => toast.success("Abuse report submitted"),
    onError: (e: Error) => toast.error(e.message)
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reviews"
        description="Reply to customers, mark helpful feedback, or report abuse."
      />
      <PublisherNav />

      {reviews.isLoading ? (
        <p className="text-sm text-muted">Loading reviews…</p>
      ) : (reviews.data ?? []).length === 0 ? (
        <EmptyState title="No reviews yet" description="Reviews appear after customers rate your listings." />
      ) : (
        <div className="space-y-4">
          {(reviews.data ?? []).map((r) => (
            <Card key={r.id} className="space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-ink">
                  {"★".repeat(r.rating)}
                  <span className="ml-2 text-sm font-normal text-muted">
                    {r.title || "Untitled review"}
                  </span>
                </p>
                <p className="text-xs text-muted">
                  Helpful {r.helpful_count ?? 0} · {new Date(r.created_at).toLocaleDateString()}
                </p>
              </div>
              {r.body ? <p className="text-sm text-ink">{r.body}</p> : null}
              {r.publisher_reply ? (
                <div className="rounded-xl bg-canvas px-3 py-2 text-sm">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">
                    Your reply
                  </p>
                  <p className="mt-1">{r.publisher_reply}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <textarea
                    className="min-h-20 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
                    placeholder="Write a public reply…"
                    value={replyDrafts[r.id] || ""}
                    onChange={(e) =>
                      setReplyDrafts((prev) => ({ ...prev, [r.id]: e.target.value }))
                    }
                  />
                  <Button
                    size="sm"
                    disabled={replyMut.isPending || !(replyDrafts[r.id] || "").trim()}
                    onClick={() =>
                      replyMut.mutate({ id: r.id, reply: (replyDrafts[r.id] || "").trim() })
                    }
                  >
                    Post reply
                  </Button>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => helpfulMut.mutate(r.id)}
                  disabled={helpfulMut.isPending}
                >
                  Mark helpful
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => reportMut.mutate(r.listing_id)}
                  disabled={reportMut.isPending}
                >
                  Report abuse
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
