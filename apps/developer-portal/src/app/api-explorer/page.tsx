"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { SnippetTabs } from "@/components/code-block";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { generateSnippets, type HttpMethod } from "@/lib/codegen";
import { site } from "@/lib/config";
import "swagger-ui-react/swagger-ui.css";

const SwaggerUI = dynamic(() => import("swagger-ui-react"), {
  ssr: false,
  loading: () => (
    <div className="rounded-2xl border border-dashed border-line bg-canvas p-10 text-center text-sm text-muted">
      Loading OpenAPI explorer…
    </div>
  )
});

type OpenApiDoc = {
  info?: { title?: string; version?: string };
  paths?: Record<string, Record<string, { summary?: string; operationId?: string; requestBody?: unknown }>>;
};

type Endpoint = {
  method: HttpMethod;
  path: string;
  summary: string;
  operationId?: string;
};

const METHODS: HttpMethod[] = ["GET", "POST", "PUT", "PATCH", "DELETE"];

export default function ApiExplorerPage() {
  const [spec, setSpec] = useState<OpenApiDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Endpoint | null>(null);
  const [token, setToken] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [tryResult, setTryResult] = useState<string>("");
  const [trying, setTrying] = useState(false);
  const [view, setView] = useState<"guided" | "swagger">("guided");

  useEffect(() => {
    fetch("/openapi.json")
      .then(async (r) => {
        if (!r.ok) throw new Error(`Failed to load OpenAPI (${r.status})`);
        return r.json();
      })
      .then((json) => {
        setSpec(json);
        const first = flatten(json)[0];
        if (first) setSelected(first);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const endpoints = useMemo(() => flatten(spec || {}), [spec]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return endpoints;
    return endpoints.filter(
      (e) =>
        e.path.toLowerCase().includes(q) ||
        e.method.toLowerCase().includes(q) ||
        e.summary.toLowerCase().includes(q)
    );
  }, [endpoints, query]);

  const snippets = useMemo(() => {
    if (!selected) return null;
    return generateSnippets({
      method: selected.method,
      path: selected.path,
      baseUrl: site.apiUrl,
      apiKey: apiKey || undefined,
      bearer: token || undefined,
      body: ["POST", "PUT", "PATCH"].includes(selected.method) ? { example: true } : undefined
    });
  }, [selected, apiKey, token]);

  async function tryIt() {
    if (!selected) return;
    setTrying(true);
    setTryResult("");
    try {
      const url = `${site.apiUrl.replace(/\/$/, "")}${selected.path}`;
      const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;
      if (token) headers.Authorization = `Bearer ${token}`;
      const init: RequestInit = { method: selected.method, headers };
      if (["POST", "PUT", "PATCH"].includes(selected.method)) {
        init.body = JSON.stringify({ message: "Hello from API Explorer" });
      }
      const res = await fetch(url, init);
      const text = await res.text();
      let pretty = text;
      try {
        pretty = JSON.stringify(JSON.parse(text), null, 2);
      } catch {
        /* keep raw */
      }
      setTryResult(`${res.status} ${res.statusText}\n\n${pretty}`);
    } catch (e) {
      setTryResult(`Request failed: ${(e as Error).message}\n\nTip: browser CORS may block cross-origin try-it. Use the generated cURL locally.`);
    } finally {
      setTrying(false);
    }
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "API Explorer" }]} />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold">API Explorer</h1>
          <p className="mt-1 text-sm text-muted">
            {spec?.info?.title || "OpenAPI"} · v{spec?.info?.version || site.version} · {endpoints.length} operations
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant={view === "guided" ? "default" : "secondary"} onClick={() => setView("guided")}>
            Guided
          </Button>
          <Button size="sm" variant={view === "swagger" ? "default" : "secondary"} onClick={() => setView("swagger")}>
            Swagger UI
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          Failed to load OpenAPI: {error}
        </Card>
      )}

      {!spec && !error && (
        <Card className="text-sm text-muted">Loading OpenAPI specification…</Card>
      )}

      {view === "swagger" && spec && (
        <Card className="overflow-hidden p-2">
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <SwaggerUI spec={spec as any} docExpansion="list" defaultModelsExpandDepth={-1} />
        </Card>
      )}

      {view === "guided" && spec && (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <Card className="max-h-[75vh] overflow-hidden p-3">
            <Input
              placeholder="Filter endpoints…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mb-3"
            />
            <div className="max-h-[65vh] space-y-1 overflow-y-auto pr-1">
              {filtered.map((ep) => {
                const active = selected?.method === ep.method && selected?.path === ep.path;
                return (
                  <button
                    key={`${ep.method}:${ep.path}`}
                    onClick={() => setSelected(ep)}
                    className={`flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm ${
                      active ? "bg-brand-soft text-ink" : "hover:bg-canvas"
                    }`}
                  >
                    <Badge tone={methodTone(ep.method)}>{ep.method}</Badge>
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-xs">{ep.path}</span>
                      <span className="block truncate text-xs text-muted">{ep.summary}</span>
                    </span>
                  </button>
                );
              })}
              {!filtered.length && <p className="p-3 text-sm text-muted">No matching endpoints.</p>}
            </div>
          </Card>

          <div className="space-y-4">
            {selected && (
              <>
                <Card>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={methodTone(selected.method)}>{selected.method}</Badge>
                    <code className="font-mono text-sm">{selected.path}</code>
                  </div>
                  <p className="mt-2 text-sm text-muted">{selected.summary || "No summary"}</p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-semibold text-muted">Bearer JWT</label>
                      <Input value={token} onChange={(e) => setToken(e.target.value)} placeholder="eyJ..." />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-semibold text-muted">API Key</label>
                      <Input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="tht_live_..." />
                    </div>
                  </div>
                  <div className="mt-4">
                    <Button onClick={tryIt} disabled={trying}>
                      {trying ? "Sending…" : "Try it"}
                    </Button>
                    <p className="mt-2 text-xs text-muted">
                      Requests go to {site.apiUrl}. CORS may block browser try-it for some hosts.
                    </p>
                  </div>
                </Card>

                {snippets && (
                  <Card>
                    <h2 className="mb-3 text-lg font-semibold">Code samples</h2>
                    <SnippetTabs
                      snippets={{
                        curl: snippets.curl,
                        javascript: snippets.javascript,
                        python: snippets.python,
                        nodejs: snippets.nodejs
                      }}
                    />
                  </Card>
                )}

                {tryResult && (
                  <Card>
                    <h2 className="mb-3 text-lg font-semibold">Response</h2>
                    <pre className="max-h-80 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">
                      {tryResult}
                    </pre>
                  </Card>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function flatten(spec: OpenApiDoc): Endpoint[] {
  const out: Endpoint[] = [];
  for (const [path, methods] of Object.entries(spec.paths || {})) {
    for (const [method, op] of Object.entries(methods || {})) {
      const m = method.toUpperCase();
      if (!METHODS.includes(m as HttpMethod)) continue;
      out.push({
        method: m as HttpMethod,
        path,
        summary: op?.summary || op?.operationId || "",
        operationId: op?.operationId
      });
    }
  }
  return out.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method));
}

function methodTone(method: string): "success" | "brand" | "warn" | "danger" | "neutral" {
  switch (method) {
    case "GET":
      return "success";
    case "POST":
      return "brand";
    case "PUT":
    case "PATCH":
      return "warn";
    case "DELETE":
      return "danger";
    default:
      return "neutral";
  }
}
