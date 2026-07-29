import type { HttpCore } from "../core/http";
import { RestError } from "../core/errors";

/**
 * Analytics resource.
 * Wire to /v2/agents/{id}/analytics when mounted; currently soft-fails with clear error.
 */
export class AnalyticsResource {
  constructor(private readonly http: HttpCore) {}

  async agent(agentId: string, params: Record<string, string | number | boolean> = {}) {
    try {
      return await this.http.get(`/v2/agents/${agentId}/analytics`, { query: params });
    } catch (err) {
      if (err instanceof RestError && err.status === 404) {
        throw new RestError(
          "Analytics endpoint not mounted yet. Enable analytics_router in main.py (Phase 2).",
          { status: 404, code: "not_implemented", details: err.details }
        );
      }
      throw err;
    }
  }
}
