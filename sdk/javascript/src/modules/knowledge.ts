import type { HttpClient } from "../http";
import type { SearchParams, SearchResponse, UploadParams } from "../types";

export class KnowledgeModule {
  constructor(private readonly http: HttpClient) {}

  async search(params: SearchParams): Promise<SearchResponse> {
    const raw = await this.http.request<any>("/v2/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: params.query,
        kb_id: params.kbId,
        top_k: params.topK ?? 5,
      }),
      signal: params.signal,
    });

    const results = Array.isArray(raw?.results)
      ? raw.results
      : Array.isArray(raw)
        ? raw
        : [];

    return { results, raw };
  }

  async upload(params: UploadParams): Promise<unknown> {
    const form = new FormData();
    const filename = params.filename || "upload.bin";

    let blob: Blob;
    if (typeof Blob !== "undefined" && params.file instanceof Blob) {
      blob = params.file;
    } else if (typeof Buffer !== "undefined" && Buffer.isBuffer(params.file)) {
      blob = new Blob([new Uint8Array(params.file)]);
    } else if (params.file instanceof ArrayBuffer) {
      blob = new Blob([params.file]);
    } else {
      blob = params.file as Blob;
    }

    form.append("file", blob, filename);
    if (params.kbId) form.append("kb_id", params.kbId);

    return this.http.request("/v2/knowledge/upload", {
      method: "POST",
      body: form,
      signal: params.signal,
      // let browser/node set multipart boundary
      headers: {},
    });
  }

  /** Conversation/message history via conversations API (JWT auth). */
  async history(opts: { conversationId?: string; limit?: number; signal?: AbortSignal } = {}) {
    if (opts.conversationId) {
      return this.http.request(`/v2/conversations/${opts.conversationId}`, {
        method: "GET",
        signal: opts.signal,
      });
    }
    const q = new URLSearchParams();
    if (opts.limit) q.set("limit", String(opts.limit));
    const qs = q.toString();
    return this.http.request(`/v2/conversations${qs ? `?${qs}` : ""}`, {
      method: "GET",
      signal: opts.signal,
    });
  }
}
