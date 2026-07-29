import type { HttpCore } from "../core/http";
import type { RequestOptions } from "../core/types";
import type { components } from "../generated/schema";

type Schemas = components["schemas"];

const ALLOWED_EXT = ["pdf", "docx", "txt", "md", "markdown"];

export class KnowledgeResource {
  constructor(private readonly http: HttpCore) {}

  listBases() {
    return this.http.get("/v2/knowledge/bases");
  }

  createBase(body: Schemas["KnowledgeBaseCreate"]) {
    return this.http.post("/v2/knowledge/bases", body);
  }

  getBase(kbId: string) {
    return this.http.get(`/v2/knowledge/bases/${kbId}`);
  }

  deleteBase(kbId: string) {
    return this.http.delete(`/v2/knowledge/bases/${kbId}`);
  }

  attachAgent(kbId: string, agentId: string) {
    return this.http.post(`/v2/knowledge/bases/${kbId}/agents/${agentId}`);
  }

  search(body: Schemas["SearchQuery"], opts?: RequestOptions) {
    return this.http.post<Schemas["SearchResponse"]>("/v2/knowledge/search", body, opts);
  }

  query(body: Schemas["RAGQueryRequest"], opts?: RequestOptions) {
    return this.http.post("/v2/knowledge/query", body, opts);
  }

  listDocuments(params: { kb_id?: string } = {}) {
    return this.http.get("/v2/knowledge/documents", {
      query: params as Record<string, string | number | boolean>,
    });
  }

  async upload(
    file: Blob | File | ArrayBuffer | Uint8Array,
    opts: { filename?: string; kbId?: string; signal?: AbortSignal } = {}
  ) {
    const filename = opts.filename || "upload.bin";
    const ext = filename.split(".").pop()?.toLowerCase() || "";
    if (ext && !ALLOWED_EXT.includes(ext === "markdown" ? "md" : ext) && !ALLOWED_EXT.includes(ext)) {
      // still allow — server validates; warn via comment only
    }
    const fields: Record<string, string> = {};
    if (opts.kbId) fields.kb_id = opts.kbId;
    return this.http.upload("/v2/knowledge/upload", file, fields, filename, {
      signal: opts.signal,
    });
  }

  reindex(docId: string) {
    return this.http.post(`/v2/knowledge/documents/${docId}/reindex`);
  }

  deleteDocument(docId: string) {
    return this.http.delete(`/v2/knowledge/documents/${docId}`);
  }
}
