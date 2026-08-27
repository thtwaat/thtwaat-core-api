"use client";

// THTWAAT Deploy Phase 6A — Preview Deployments. Read-only status + manual
// close, integrated into the existing GitHub Connect section of the
// existing Deployment Center (GitHubPanel.tsx) rather than a new dashboard
// — same siteId scope, same RBAC (canManage), same vertically-stacked
// "<div className='mt-6'>" section convention every other panel here uses.
//
// Previews are only ever CREATED/advanced/torn down by the GitHub webhook
// itself (a PR opened/synchronize/reopened/closed) — this component never
// triggers a build, only displays lifecycle state and offers an early
// manual close (async — see previewDeploymentsApi.close).

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { previewDeploymentsApi } from "@/lib/services";
import {
  previewDeployStatusLabel,
  previewDeployStatusTone,
  previewIsActive,
  shortCommit,
  type PreviewDeployment
} from "@/lib/preview-deployments";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/misc";
import { cn, formatDate } from "@/lib/utils";

const PREVIEWS_PER_PAGE = 30;

function prUrl(preview: PreviewDeployment): string | null {
  if (!preview.github_repository_owner || !preview.github_repository_name) return null;
  return `https://github.com/${preview.github_repository_owner}/${preview.github_repository_name}/pull/${preview.pr_number}`;
}

export function PreviewDeploymentsPanel({ siteId, canManage }: { siteId: string; canManage: boolean }) {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<PreviewDeployment[]>([]);

  const previewsQ = useQuery({
    queryKey: ["preview-deployments", siteId, page],
    queryFn: () => previewDeploymentsApi.list(siteId, page, PREVIEWS_PER_PAGE),
    enabled: Boolean(siteId),
    refetchInterval: (q) => {
      const rows = q.state.data?.items || [];
      const busy = rows.some((p) => ["queued", "building"].includes(p.status));
      return busy ? 4000 : false;
    }
  });

  useEffect(() => {
    if (!previewsQ.data) return;
    setItems((prev) => (page === 1 ? previewsQ.data.items : [...prev, ...previewsQ.data.items]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewsQ.data]);

  useEffect(() => {
    setPage(1);
    setItems([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId]);

  const closeM = useMutation({
    mutationFn: (previewId: string) => previewDeploymentsApi.close(siteId, previewId),
    onSuccess: () => {
      toast.success("Preview closing");
      void qc.invalidateQueries({ queryKey: ["preview-deployments", siteId] });
    },
    onError: (err: Error) => toast.error(err.message)
  });

  if (!siteId) return null;

  const rows = items;

  return (
    <div className="mt-6">
      <h4 className="mb-2 text-sm font-semibold text-ink">Preview Deployments</h4>
      <p className="mb-3 text-xs text-muted">
        A pull request against the connected branch automatically gets its own preview URL — closed automatically
        when the PR closes.
      </p>

      {previewsQ.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading previews…
        </p>
      ) : previewsQ.isError ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {(previewsQ.error as Error).message}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No preview deployments yet"
          description="Open a pull request against the connected branch to see a preview here."
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((p) => {
            const website = p.urls?.website;
            const link = prUrl(p);
            return (
              <li
                key={p.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2.5"
              >
                <div>
                  <p className="text-sm font-medium">
                    {link ? (
                      <a href={link} target="_blank" rel="noreferrer" className="text-brand underline">
                        PR #{p.pr_number}
                      </a>
                    ) : (
                      `PR #${p.pr_number}`
                    )}
                    <span className="ml-2 text-xs text-muted">
                      {p.branch} · {shortCommit(p.commit_sha)}
                    </span>
                  </p>
                  <p className="text-xs text-muted">
                    Updated {formatDate(p.updated_at)}
                    {p.expires_at && previewIsActive(p) ? ` · expires ${formatDate(p.expires_at)}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={previewDeployStatusTone(p.status)}>{previewDeployStatusLabel(p.status)}</Badge>
                  {website && (
                    <a
                      href={website}
                      target="_blank"
                      rel="noreferrer"
                      className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "inline-flex")}
                    >
                      Open
                    </a>
                  )}
                  {canManage && previewIsActive(p) && (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => closeM.mutate(p.id)}
                      disabled={closeM.isPending}
                    >
                      Close
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {previewsQ.data && previewsQ.data.total > page * PREVIEWS_PER_PAGE && (
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => setPage((p) => p + 1)}
          disabled={previewsQ.isFetching}
        >
          {previewsQ.isFetching ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
          Load more previews
        </Button>
      )}
    </div>
  );
}
