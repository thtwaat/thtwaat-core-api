"use client";

// THTWAAT Deploy — upload a static HTML file or a ZIP and get a live
// *.thtwaat.com URL with SSL, reusing the existing Domain Manager / SSL
// Manager. A separate entry point from the AI Software Factory deploy flow
// above (Deployment Center) — this never touches that flow's state.

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { toast } from "sonner";
import { staticSitesApi } from "@/lib/services";
import {
  frameworkLabel,
  runtimeLabel,
  staticDeployStatusLabel,
  staticDeployStatusTone,
  type StaticSiteDeployment
} from "@/lib/static-sites";
import { githubCallbackErrorMessage } from "@/lib/github";
import { useAuth } from "@/lib/auth";
import { canDeleteStudioProjects } from "@/lib/permissions";
import { cn, formatDate } from "@/lib/utils";
import { Card, CardHeader, Badge } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { Progress, EmptyState } from "@/components/ui/misc";
import { EnvVarsPanel } from "./EnvVarsPanel";
import { GitHubPanel } from "./GitHubPanel";

const ALLOWED_EXT = [".html", ".zip"];

export function StaticDeployPanel() {
  const { user } = useAuth();
  const canDeploy = canDeleteStudioProjects(user?.role);
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();

  const [siteName, setSiteName] = useState("");
  const [siteId, setSiteId] = useState<string>("");
  const [dragOver, setDragOver] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [phase, setPhase] = useState<"" | "uploading" | "deploying">("");
  const [result, setResult] = useState<StaticSiteDeployment | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const sites = useQuery({ queryKey: ["static-sites"], queryFn: staticSitesApi.list });
  const activeSiteId = siteId || sites.data?.items?.[0]?.id || "";

  // GitHub App callback landing: app/static_sites/github_router.py redirects
  // here as /app/studio?site_id=...&github=connected (or &github_error=...)
  // after the user finishes (or cancels) authorizing on github.com. Read it
  // once on mount, then strip those params so a refresh or back-navigation
  // doesn't re-show the toast or re-select the site. window.location is used
  // instead of next/navigation's useSearchParams() so this doesn't force a
  // Suspense boundary onto this already-large client page for one-time,
  // client-only param handling.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const urlSiteId = params.get("site_id");
    const githubStatus = params.get("github");
    const githubError = params.get("github_error");
    if (!urlSiteId && !githubStatus && !githubError) return;

    if (urlSiteId) setSiteId(urlSiteId);
    if (githubStatus === "connected") {
      toast.success("GitHub connected");
      void qc.invalidateQueries({ queryKey: ["github-connection"] });
    } else if (githubError) {
      toast.error(githubCallbackErrorMessage(githubError));
    }

    params.delete("site_id");
    params.delete("github");
    params.delete("github_error");
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deployments = useQuery({
    queryKey: ["static-site-deployments", activeSiteId],
    queryFn: () => staticSitesApi.listDeployments(activeSiteId),
    enabled: Boolean(activeSiteId),
    refetchInterval: (q) => {
      const rows = q.state.data?.items || [];
      const busy = rows.some((d) =>
        ["queued", "validating", "runtime_starting", "provisioning_ssl"].includes(d.status)
      );
      return busy ? 4000 : false;
    }
  });

  const createSite = useMutation({
    mutationFn: (name: string) => staticSitesApi.create(name),
    onSuccess: (site) => {
      setSiteId(site.id);
      qc.invalidateQueries({ queryKey: ["static-sites"] });
      return site;
    }
  });

  const rollbackM = useMutation({
    mutationFn: (deploymentId?: string) => staticSitesApi.rollback(activeSiteId, { deployment_id: deploymentId }),
    onSuccess: () => {
      toast.success("Rolled back");
      qc.invalidateQueries({ queryKey: ["static-site-deployments", activeSiteId] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  async function onFiles(files: FileList | File[] | null | undefined) {
    const file = files && files[0];
    if (!file) return;
    setFileError(null);
    setResult(null);

    const ext = ("." + (file.name.split(".").pop() || "")).toLowerCase();
    if (!ALLOWED_EXT.includes(ext)) {
      setFileError("Unsupported file type. Only .html and .zip are supported.");
      return;
    }

    let currentSiteId = activeSiteId;
    if (!currentSiteId) {
      if (!siteName.trim()) {
        setFileError("Name your site first (e.g. \"My Website\")");
        return;
      }
      try {
        const site = await createSite.mutateAsync(siteName.trim());
        currentSiteId = site.id;
      } catch (e) {
        setFileError(e instanceof Error ? e.message : "Could not create site");
        return;
      }
    }

    setPhase("uploading");
    setUploadPct(0);
    try {
      const deployment = await staticSitesApi.uploadWithProgress(
        currentSiteId,
        file,
        { domainMode: "free_subdomain" },
        (pct) => {
          setUploadPct(pct);
          if (pct >= 100) setPhase("deploying");
        }
      );
      setResult(deployment);
      if (deployment.status === "failed") {
        toast.error(deployment.error || "Deployment failed");
      } else if (deployment.live) {
        toast.success("🎉 Deployment successful");
      } else {
        toast.message("Deployment created — SSL is still provisioning");
      }
      qc.invalidateQueries({ queryKey: ["static-sites"] });
      qc.invalidateQueries({ queryKey: ["static-site-deployments", currentSiteId] });
      setSiteId(currentSiteId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Deployment failed");
    } finally {
      setPhase("");
      setUploadPct(null);
    }
  }

  if (!canDeploy) return null;

  const rows = deployments.data?.items || [];
  const website = result?.urls?.website;

  return (
    <Card>
      <CardHeader
        title="THTWAAT Deploy"
        description="Drop an index.html or a .zip and get a live *.thtwaat.com URL with SSL — no build required."
      />

      {!activeSiteId && (
        <div className="mb-4">
          <Label htmlFor="static-site-name">Site name</Label>
          <Input
            id="static-site-name"
            placeholder="My Website"
            value={siteName}
            onChange={(e) => setSiteName(e.target.value)}
            aria-label="New static site name"
          />
        </div>
      )}

      {sites.data && sites.data.items.length > 1 && (
        <div className="mb-4">
          <Label htmlFor="static-site-select">Site</Label>
          <Select
            id="static-site-select"
            value={activeSiteId}
            onChange={(e) => setSiteId(e.target.value)}
          >
            {sites.data.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
      )}

      <div
        className={cn(
          "rounded-2xl border border-dashed px-6 py-10 text-center",
          dragOver ? "border-brand bg-brand-soft/30" : "border-line bg-canvas"
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          void onFiles(e.dataTransfer.files);
        }}
        role="region"
        aria-label="Drop HTML or ZIP to deploy"
      >
        <p className="text-sm font-medium">Drop HTML or ZIP here</p>
        <p className="mt-1 text-xs text-muted">
          Static HTML/CSS/JS, a Vite project, or a Next.js project (with{" "}
          <code>output: &quot;standalone&quot;</code>) — built in an isolated sandbox
        </p>
        <Input
          type="file"
          accept=".html,.zip"
          className="mx-auto mt-4 max-w-xs"
          onChange={(e) => void onFiles(e.target.files)}
          disabled={phase !== ""}
          aria-label="Choose an HTML or ZIP file"
        />

        {fileError && <p className="mt-3 text-sm text-red-600">{fileError}</p>}

        {phase === "uploading" && uploadPct != null && (
          <div className="mx-auto mt-4 max-w-sm">
            <Progress value={uploadPct} />
            <p className="mt-1 text-xs text-muted">Uploading… {uploadPct}%</p>
          </div>
        )}
        {phase === "deploying" && (
          <p className="mt-4 text-xs text-muted">
            Detecting project type, building if needed, publishing, and provisioning SSL — Vite and
            Next.js projects build in an isolated sandbox and can take a few minutes. Next.js
            deployments also start an isolated runtime container and health-check it before going
            live — your previous version stays live until the new one passes.
          </p>
        )}
      </div>

      {result && (
        <div className="mt-4 rounded-2xl border border-line bg-canvas p-4">
          {result.status === "failed" ? (
            <>
              <p className="font-semibold text-red-600">Deployment failed</p>
              <p className="mt-1 text-sm text-muted">Reason: {result.error || "Unknown error"}</p>
            </>
          ) : (
            <>
              <p className="font-semibold">
                {result.live ? "🎉 Deployment successful" : "Deployment created"}
              </p>
              {frameworkLabel(result.framework) && (
                <p className="mt-1 text-xs text-muted">
                  Framework: {frameworkLabel(result.framework)}
                  {result.runtime_type === "node" && (
                    <>
                      {" "}
                      · Runtime: {runtimeLabel(result.runtime_type)}
                      {result.health_status && ` (${result.health_status})`}
                    </>
                  )}
                </p>
              )}
              {website && (
                <div className="mt-2 flex items-center gap-3">
                  <a href={website} target="_blank" rel="noreferrer" className="text-sm text-brand underline">
                    {website}
                  </a>
                  <a
                    href={website}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "inline-flex")}
                  >
                    Open Website
                  </a>
                </div>
              )}
              {!result.live && (
                <p className="mt-1 text-xs text-muted">SSL is still provisioning — this page auto-refreshes.</p>
              )}
            </>
          )}
        </div>
      )}

      {activeSiteId && (
        <div className="mt-6">
          <h4 className="mb-2 text-sm font-semibold text-ink">History</h4>
          {rows.length === 0 ? (
            <EmptyState title="No deployments yet" description="Upload a file above to go live." />
          ) : (
            <ul className="space-y-2">
              {rows.map((d) => (
                <li
                  key={d.id}
                  className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5"
                >
                  <div>
                    <p className="text-sm font-medium">
                      v{d.version} · {frameworkLabel(d.framework) || d.source_type.toUpperCase()}
                      {d.runtime_type === "node" && (
                        <span className="ml-2 text-xs text-muted">({runtimeLabel(d.runtime_type)})</span>
                      )}
                      {d.is_current && <span className="ml-2 text-xs text-muted">(current)</span>}
                    </p>
                    <p className="text-xs text-muted">{formatDate(d.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={staticDeployStatusTone(d.status)}>{staticDeployStatusLabel(d.status)}</Badge>
                    {d.urls?.website && (
                      <a
                        href={d.urls.website}
                        target="_blank"
                        rel="noreferrer"
                        className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "inline-flex")}
                      >
                        Open
                      </a>
                    )}
                    {!d.is_current && d.status === "completed" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => rollbackM.mutate(d.id)}
                        disabled={rollbackM.isPending}
                      >
                        Rollback
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <GitHubPanel siteId={activeSiteId} canManage={canDeploy} />

      <EnvVarsPanel
        siteId={activeSiteId}
        framework={rows.find((d) => d.is_current)?.framework ?? rows[0]?.framework}
        canManage={canDeploy}
      />
    </Card>
  );
}
