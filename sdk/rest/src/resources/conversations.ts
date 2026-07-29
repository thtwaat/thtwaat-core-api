import type { HttpCore } from "../core/http";
import type { components } from "../generated/schema";

type Schemas = components["schemas"];

export class ConversationsResource {
  constructor(private readonly http: HttpCore) {}

  list(params: { skip?: number; limit?: number } = {}) {
    return this.http.get("/v2/conversations", {
      query: params as Record<string, string | number | boolean>,
    });
  }

  create(body: Schemas["ConversationCreate"]) {
    return this.http.post("/v2/conversations", body);
  }

  get(conversationId: string) {
    return this.http.get(`/v2/conversations/${conversationId}`);
  }

  delete(conversationId: string) {
    return this.http.delete(`/v2/conversations/${conversationId}`);
  }

  sendMessage(conversationId: string, body: { content: string }) {
    return this.http.post(`/v2/conversations/${conversationId}/messages`, body);
  }
}
