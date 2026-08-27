"use client";

// THTWAAT Deploy Phase 5B — GitHub Connect (UI over the Phase 5 backend).
// Scoped to one static site (the same `siteId` StaticDeployPanel already
// tracks), mirroring EnvVarsPanel.tsx's shape/conventions exactly — this is
// that site's "GitHub" settings surface, rendered as its own section rather
// than a new route.
//
// This component never constructs a GitHub URL, handles a token, or stores
// OAuth state — "Connect GitHub" only follows the backend-issued
// authorize_url (a full browser navigation), and every repository/branch
// list comes from the THTWAAT backend, never GitHub directly.
//
// THTWAAT Deploy Phase 5C — once a repository+branch is selected, a push to
// that branch auto-deploys server-side (see app/static_sites/
// github_webhook_router.py); AutoDeployStatus below is a read-only view of
// that (no configuration lives in the frontend — the webhook URL/secret are
// server config, never something a user pastes in here).
//
// THTWAAT Deploy Phase 6A — a pull request against that same branch now
// also gets its own Preview Deployment automatically (see
// PreviewDeploymentsPanel.tsx below) — same "no frontend configuration"
// principle; the webhook does all the work.

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Github, Loader2 } from "lucide-react";
import { githubApi, staticSitesApi } from "@/lib/services";
import {
  GITHUB_BRANCHES_PER_PAGE,
  GITHUB_REPOSITORIES_PER_PAGE,
  buildSelectPayload,
  connectionStatusLabel,
  connectionStatusTone,
  githubApiErrorMessage,
  hasSelectedRepository,
  repositoryFullName,
  visibilityLabel,
  type GitHubBranch,
  type GitHubRepository
} from "@/lib/github";
import { staticDeployStatusLabel, staticDeployStatusTone } from "@/lib/static-sites";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { PreviewDeploymentsPanel } from "./PreviewDeploymentsPanel";

// THTWAAT Deploy Phase 5C — read-only "Auto Deploy" status card. Reuses the
// SAME query key StaticDeployPanel.tsx already fetches deployment history
// with (["static-site-deployments", siteId]) so this never issues a
// duplicate network request; deployments are ordered version-desc by the
// backend, so items[0] is always the latest, whether it came from a manual
// upload or a GitHub push.
function AutoDeployStatus({ siteId }: { siteId: string }) {
  const deploymentsQ = useQuery({
    queryKey: ["static-site-deployments", siteId],
    queryFn: () => staticSitesApi.listDeployments(siteId),
    enabled: Boolean(siteId)
  });

  const latest = deploymentsQ.data?.items?.[0] ?? null;

  return (
    <div className="rounded-2xl border border-line bg-canvas p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-ink">Auto Deploy</p>
        <Badge tone="success">Enabled</Badge>
      </div>
      <p className="mt-1 text-xs text-muted">A push to the connected branch deploys automatically.</p>
      {latest && latest.source_provider === "github" && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Latest commit</p>
            <p className="font-mono text-sm text-ink">{(latest.github_commit_sha || "").slice(0, 12) || "—"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Deployment</p>
            <Badge tone={staticDeployStatusTone(latest.status)}>{staticDeployStatusLabel(latest.status)}</Badge>
          </div>
        </div>
      )}
    </div>
  );
}

function RepositoryPicker({
  siteId,
  onCancel,
  onDone
}: {
  siteId: string;
  onCancel: () => void;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  const [reposPage, setReposPage] = useState(1);
  const [repoItems, setRepoItems] = useState<GitHubRepository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepository | null>(null);
  const [branch, setBranch] = useState("");

  const reposQ = useQuery({
    queryKey: ["github-repositories", siteId, reposPage],
    queryFn: () => githubApi.listRepositories(siteId, reposPage, GITHUB_REPOSITORIES_PER_PAGE)
  });

  useEffect(() => {
    if (!reposQ.data) return;
    setRepoItems((prev) => (reposPage === 1 ? reposQ.data.items : [...prev, ...reposQ.data.items]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reposQ.data]);

  const branchesQ = useQuery({
    queryKey: ["github-branches", siteId, selectedRepo?.owner, selectedRepo?.name],
    queryFn: () => githubApi.listBranches(siteId, selectedRepo!.owner, selectedRepo!.name, 1, GITHUB_BRANCHES_PER_PAGE),
    enabled: Boolean(selectedRepo)
  });

  const selectM = useMutation({
    mutationFn: () =>
      githubApi.selectRepository(
        siteId,
        buildSelectPayload({ owner: selectedRepo!.owner, name: selectedRepo!.name, branch })
      ),
    onSuccess: () => {
      toast.success("Repository connected");
      void qc.invalidateQueries({ queryKey: ["github-connection", siteId] });
      onDone();
    },
    onError: (err) => toast.error(githubApiErrorMessage(err))
  });

  function pickRepo(repo: GitHubRepository) {
    setSelectedRepo(repo);
    setBranch(repo.default_branch || "");
  }

  return (
    <div className="mt-4 space-y-4 rounded-2xl border border-line bg-canvas p-4">
      <div>
        <h5 className="text-sm font-semibold text-ink">Select a repository</h5>
        {reposQ.isLoading ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading repositories…
          </p>
        ) : reposQ.isError ? (
          <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {githubApiErrorMessage(reposQ.error)}
          </div>
        ) : repoItems.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              title="No accessible GitHub repositories found."
              description="Grant this GitHub App access to a repository, then try again."
            />
          </div>
        ) : (
          <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto">
            {repoItems.map((repo) => (
              <li key={repo.repository_id}>
                <button
                  type="button"
                  onClick={() => pickRepo(repo)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left text-sm",
                    selectedRepo?.repository_id === repo.repository_id
                      ? "border-brand bg-brand-soft/20"
                      : "border-line hover:border-brand/60"
                  )}
                >
                  <span className="font-medium text-ink">{repo.full_name}</span>
                  <Badge tone={repo.private ? "neutral" : "success"}>{visibilityLabel(repo.private)}</Badge>
                </button>
              </li>
            ))}
          </ul>
        )}
        {reposQ.data && reposQ.data.items.length === GITHUB_REPOSITORIES_PER_PAGE && (
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => setReposPage((p) => p + 1)}
            disabled={reposQ.isFetching}
          >
            {reposQ.isFetching ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
            Load more repositories
          </Button>
        )}
      </div>

      {selectedRepo && (
        <div>
          <h5 className="text-sm font-semibold text-ink">Select a branch</h5>
          {branchesQ.isLoading ? (
            <p className="mt-3 flex items-center gap-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading branches…
            </p>
          ) : branchesQ.isError ? (
            <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {githubApiErrorMessage(branchesQ.error)}
            </div>
          ) : (branchesQ.data?.items.length || 0) === 0 ? (
            <div className="mt-3">
              <EmptyState title="No branches found for this repository." />
            </div>
          ) : (
            <Select className="mt-3 max-w-xs" value={branch} onChange={(e) => setBranch(e.target.value)}>
              <option value="" disabled>
                Choose a branch…
              </option>
              {branchesQ.data!.items.map((b: GitHubBranch) => (
                <option key={b.name} value={b.name}>
                  {b.name}
                  {b.protected ? " (protected)" : ""}
                </option>
              ))}
            </Select>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={onCancel} disabled={selectM.isPending}>
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => selectM.mutate()}
          disabled={!selectedRepo || !branch || selectM.isPending}
        >
          {selectM.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
          Save
        </Button>
      </div>
    </div>
  );
}

export function GitHubPanel({ siteId, canManage }: { siteId: string; canManage: boolean }) {
  const qc = useQueryClient();
  const [showPicker, setShowPicker] = useState(false);

  const connectionQ = useQuery({
    queryKey: ["github-connection", siteId],
    queryFn: () => githubApi.getConnection(siteId),
    enabled: Boolean(siteId)
  });

  useEffect(() => {
    setShowPicker(false);
  }, [siteId]);

  const connectM = useMutation({
    mutationFn: () => githubApi.connect(siteId),
    onSuccess: (data) => {
      // Follow the backend-issued authorize_url with a full browser
      // navigation — never fetched, never parsed, never stored.
      window.location.href = data.authorize_url;
    },
    onError: (err) => toast.error(githubApiErrorMessage(err))
  });

  const disconnectM = useMutation({
    mutationFn: () => githubApi.disconnect(siteId),
    onSuccess: () => {
      toast.success("GitHub disconnected");
      setShowPicker(false);
      void qc.invalidateQueries({ queryKey: ["github-connection", siteId] });
    },
    onError: (err) => toast.error(githubApiErrorMessage(err))
  });

  if (!siteId) {
    return (
      <div className="mt-6">
        <h4 className="mb-2 text-sm font-semibold text-ink">GitHub</h4>
        <EmptyState
          title="Create a site first"
          description="Upload a site above, then come back here to connect a GitHub repository."
        />
      </div>
    );
  }

  if (!canManage) {
    return (
      <div className="mt-6">
        <h4 className="mb-2 text-sm font-semibold text-ink">GitHub</h4>
        <EmptyState
          title="You don't have permission to manage GitHub connections."
          description="Ask a company owner or admin for access."
        />
      </div>
    );
  }

  const connection = connectionQ.data ?? null;

  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Github className="h-4 w-4 text-ink" />
          <h4 className="text-sm font-semibold text-ink">GitHub</h4>
        </div>
        {!connectionQ.isLoading && (
          <Badge tone={connectionStatusTone(connection)}>{connectionStatusLabel(connection)}</Badge>
        )}
      </div>

      {connectionQ.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Checking GitHub connection…
        </p>
      ) : connectionQ.isError ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {githubApiErrorMessage(connectionQ.error)}
        </div>
      ) : !connection ? (
        <div>
          <EmptyState
            title="Not connected"
            description="Connect GitHub to deploy this project from a repository."
          />
          <Button className="mt-4" onClick={() => connectM.mutate()} disabled={connectM.isPending}>
            {connectM.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
            Connect GitHub
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-2xl border border-line bg-canvas p-4">
            <p className="text-sm text-muted">
              Connected as <span className="font-medium text-ink">{connection.github_username}</span>
            </p>
            {hasSelectedRepository(connection) ? (
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">Repository</p>
                  <p className="text-sm font-medium text-ink">{repositoryFullName(connection)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">Branch</p>
                  <p className="text-sm font-medium text-ink">{connection.selected_branch}</p>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">No repository selected yet.</p>
            )}
          </div>

          {hasSelectedRepository(connection) && <AutoDeployStatus siteId={siteId} />}
          {hasSelectedRepository(connection) && <PreviewDeploymentsPanel siteId={siteId} canManage={canManage} />}

          {!showPicker && (
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setShowPicker(true)}>
                {hasSelectedRepository(connection) ? "Change Repository" : "Select Repository"}
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  if (window.confirm("Disconnect this GitHub repository from this THTWAAT project?")) {
                    disconnectM.mutate();
                  }
                }}
                disabled={disconnectM.isPending}
              >
                {disconnectM.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                Disconnect
              </Button>
            </div>
          )}

          {showPicker && (
            <RepositoryPicker siteId={siteId} onCancel={() => setShowPicker(false)} onDone={() => setShowPicker(false)} />
          )}
        </div>
      )}
    </div>
  );
}
