import type { HttpClient } from "../http";
import type { AgentInfo } from "../types";

export class AgentModule {
  constructor(
    private readonly http: HttpClient,
    private readonly getAgentId: () => string | undefined
  ) {}

  async info(agentId?: string): Promise<AgentInfo> {
    const id = agentId || this.getAgentId();
    if (!id) {
      // Public widget config path needs widget_id; for agent id use v2
      throw new Error("agentId is required. Pass agentId or set client options.");
    }
    return this.http.request<AgentInfo>(`/v2/agents/${id}`, { method: "GET" });
  }

  async status(agentId?: string): Promise<{ status: string; raw: AgentInfo }> {
    const raw = await this.info(agentId);
    return { status: String(raw.status || "UNKNOWN"), raw };
  }

  async publish(agentId?: string): Promise<unknown> {
    const id = agentId || this.getAgentId();
    if (!id) throw new Error("agentId is required");
    return this.http.request(`/api/v1/agents/${id}/publish`, { method: "POST" });
  }

  async embed(agentId?: string): Promise<unknown> {
    const id = agentId || this.getAgentId();
    if (!id) throw new Error("agentId is required");
    return this.http.request(`/api/v1/agents/${id}/embed`, { method: "GET" });
  }
}
