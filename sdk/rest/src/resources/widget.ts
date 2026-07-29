import type { HttpCore } from "../core/http";

export class WidgetResource {
  constructor(private readonly http: HttpCore) {}

  /** Public widget config by widget_id */
  getConfig(widgetId: string) {
    return this.http.get(`/public/v1/widget/${widgetId}`);
  }

  /** Dashboard embed snippets for an agent */
  embed(agentId: string) {
    return this.http.get(`/api/v1/agents/${agentId}/embed`);
  }

  getAgentWidget(agentId: string) {
    return this.http.get(`/api/v1/agents/${agentId}/widget`);
  }

  updateAgentWidget(agentId: string, body: unknown) {
    return this.http.patch(`/api/v1/agents/${agentId}/widget`, body);
  }

  /** Absolute CDN script URL helper */
  scriptUrl(baseURL?: string): string {
    const base = (baseURL || this.http.baseURL).replace(/\/$/, "");
    return `${base}/widget.js`;
  }
}
