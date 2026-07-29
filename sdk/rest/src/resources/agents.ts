import type { HttpCore } from "../core/http";
import type { components } from "../generated/schema";
import type { RequestOptions } from "../core/types";

type Schemas = components["schemas"];

export class AgentsResource {
  constructor(private readonly http: HttpCore) {}

  list(params: { is_template?: boolean } = {}) {
    return this.http.get<Schemas["AgentResponse"][]>("/v2/agents", {
      query: params as Record<string, string | number | boolean>,
    });
  }

  create(body: Schemas["AgentCreate"]) {
    return this.http.post<Schemas["AgentResponse"]>("/v2/agents", body);
  }

  get(agentId: string) {
    return this.http.get<Schemas["AgentResponse"]>(`/v2/agents/${agentId}`);
  }

  publish(agentId: string) {
    return this.http.post<Schemas["PublishResponse"]>(`/api/v1/agents/${agentId}/publish`);
  }

  unpublish(agentId: string) {
    return this.http.post(`/api/v1/agents/${agentId}/unpublish`);
  }

  listApiKeys(agentId: string) {
    return this.http.get(`/api/v1/agents/${agentId}/api-keys`);
  }

  createApiKey(agentId: string, body: Schemas["AgentApiKeyCreate"]) {
    return this.http.post(`/api/v1/agents/${agentId}/api-keys`, body);
  }

  rotateApiKey(agentId: string, keyId: string) {
    return this.http.post(`/api/v1/agents/${agentId}/api-keys/${keyId}/rotate`);
  }

  disableApiKey(agentId: string, keyId: string) {
    return this.http.post(`/api/v1/agents/${agentId}/api-keys/${keyId}/disable`);
  }

  deleteApiKey(agentId: string, keyId: string) {
    return this.http.delete(`/api/v1/agents/${agentId}/api-keys/${keyId}`);
  }

  getWidget(agentId: string) {
    return this.http.get(`/api/v1/agents/${agentId}/widget`);
  }

  updateWidget(agentId: string, body: Schemas["WidgetConfigUpdate"]) {
    return this.http.patch(`/api/v1/agents/${agentId}/widget`, body);
  }

  embed(agentId: string) {
    return this.http.get<Schemas["EmbedSnippetResponse"]>(`/api/v1/agents/${agentId}/embed`);
  }

  /** Public chat (API key auth) */
  chat(
    body: Schemas["PublicChatRequest"],
    opts?: RequestOptions
  ) {
    return this.http.post<Schemas["PublicChatResponse"]>("/public/v1/chat", body, opts);
  }

  streamChat(body: Schemas["PublicChatRequest"], opts?: RequestOptions) {
    return this.http.streamSSE("/public/v1/chat/stream", body, opts);
  }
}
