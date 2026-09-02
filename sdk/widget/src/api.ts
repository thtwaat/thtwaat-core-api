import type {
  GeneratedImage,
  ImageContentBlock,
  PublicChatResponse,
  PublicImageResponse,
  PublicVoiceResponse,
  PublicWidgetConfigResponse,
} from "./types";

export type { GeneratedImage };

/**
 * The backend's global error handler returns {"error": ..., "code": ...}
 * (see app/api/exceptions.py) — not FastAPI's default {"detail": ...}.
 * Only used by the new voice/image methods below; the pre-existing chat/
 * lead/handoff methods keep their original (unrelated) error parsing as-is.
 */
function extractBackendError(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "error" in data) {
    const err = (data as { error: unknown }).error;
    if (typeof err === "string") return err;
    if (err && typeof err === "object" && "message" in err) {
      const msg = (err as { message: unknown }).message;
      if (typeof msg === "string") return msg;
    }
  }
  return fallback;
}

export type StreamEvent =
  | { type: "thinking"; stage?: string; message?: string }
  | { type: "token"; text: string }
  | { type: "done"; conversation_id: string; reply: string; handoff?: boolean; status?: string }
  | { type: "error"; message: string };

export class WidgetApiClient {
  constructor(
    private readonly apiBaseUrl: string,
    private readonly apiKey: string
  ) {}

  private url(path: string): string {
    return `${this.apiBaseUrl.replace(/\/$/, "")}${path}`;
  }

  async chat(
    message: string,
    sessionId: string | null,
    metadata: Record<string, unknown> = {},
    images?: ImageContentBlock[]
  ): Promise<PublicChatResponse> {
    const res = await fetch(this.url("/public/v1/chat"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        api_key: this.apiKey,
        message,
        session_id: sessionId,
        metadata,
        ...(images && images.length ? { images } : {}),
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : data.detail?.message || `Chat failed (${res.status})`;
      throw new Error(detail);
    }
    return data as PublicChatResponse;
  }

  async captureLead(
    sessionId: string | null,
    lead: Record<string, unknown>,
    metadata: Record<string, unknown> = {}
  ): Promise<{ conversation_id: string; lead: Record<string, unknown> }> {
    const res = await fetch(this.url("/public/v1/leads"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        api_key: this.apiKey,
        session_id: sessionId,
        lead,
        metadata,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(
        typeof data.detail === "string" ? data.detail : `Lead capture failed (${res.status})`
      );
    }
    return data;
  }

  async requestHandoff(sessionId: string, reason?: string): Promise<void> {
    const res = await fetch(this.url("/public/v1/handoff"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        api_key: this.apiKey,
        session_id: sessionId,
        reason,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(
        typeof data.detail === "string" ? data.detail : `Handoff failed (${res.status})`
      );
    }
  }

  async sessionMessages(
    sessionId: string,
    after?: string | null
  ): Promise<{ conversation_id: string; status: string; messages: Array<{ id: string; role: string; content: string }> }> {
    const qs = after ? `?after=${encodeURIComponent(after)}` : "";
    const res = await fetch(this.url(`/public/v1/sessions/${sessionId}/messages${qs}`), {
      headers: { Authorization: `Bearer ${this.apiKey}` },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(
        typeof data.detail === "string" ? data.detail : `Session fetch failed (${res.status})`
      );
    }
    return data;
  }

  /**
   * Voice turn: recorded audio in, transcript + spoken reply out.
   * multipart/form-data, per the existing backend contract
   * (POST /public/v1/agents/{slug}/voice — audio: File, api_key/session_id: Form fields).
   */
  async voiceChat(
    agentSlug: string,
    audio: Blob,
    filename: string,
    sessionId: string | null
  ): Promise<PublicVoiceResponse> {
    const form = new FormData();
    form.append("audio", audio, filename);
    form.append("api_key", this.apiKey);
    if (sessionId) form.append("session_id", sessionId);

    const res = await fetch(this.url(`/public/v1/agents/${encodeURIComponent(agentSlug)}/voice`), {
      method: "POST",
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(extractBackendError(data, `Voice request failed (${res.status})`));
    }
    return data as PublicVoiceResponse;
  }

  /**
   * Image generation: text prompt in, generated image(s) out.
   * POST /public/v1/agents/{slug}/image, JSON body { prompt }.
   */
  async generateImage(
    agentSlug: string,
    prompt: string,
    sessionId: string | null,
    metadata: Record<string, unknown> = {}
  ): Promise<PublicImageResponse> {
    const res = await fetch(this.url(`/public/v1/agents/${encodeURIComponent(agentSlug)}/image`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: this.apiKey,
        prompt,
        session_id: sessionId,
        metadata,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(extractBackendError(data, `Image generation failed (${res.status})`));
    }
    return data as PublicImageResponse;
  }

  /**
   * Fetch public widget config (capability flags + theming) for an agent
   * slug. Called at most once per widget init (see Widget.ts). Never throws
   * — any failure (network, 401, 404, malformed body) returns null so the
   * widget always keeps working for text chat even if this can't load.
   */
  async getWidgetConfig(agentSlug: string): Promise<PublicWidgetConfigResponse | null> {
    try {
      const res = await fetch(this.url(`/public/v1/agents/${encodeURIComponent(agentSlug)}/widget-config`), {
        headers: { Authorization: `Bearer ${this.apiKey}` },
      });
      if (!res.ok) return null;
      const data = await res.json().catch(() => null);
      if (!data || typeof data !== "object" || !data.capabilities) return null;
      return data as PublicWidgetConfigResponse;
    } catch {
      return null;
    }
  }

  /**
   * SSE streaming when available. Yields thinking + token chunks.
   */
  async *streamChat(
    message: string,
    sessionId: string | null,
    metadata: Record<string, unknown> = {},
    images?: ImageContentBlock[]
  ): AsyncGenerator<StreamEvent> {
    let res: Response;
    try {
      res = await fetch(this.url("/public/v1/chat/stream"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          api_key: this.apiKey,
          message,
          session_id: sessionId,
          metadata,
          ...(images && images.length ? { images } : {}),
        }),
      });
    } catch {
      return;
    }

    if (!res.ok || !res.body) {
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const lines = part.split("\n");
        let event = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        try {
          const payload = JSON.parse(data);
          if (event === "thinking") {
            yield {
              type: "thinking",
              stage: payload.stage,
              message: payload.message || "Thinking…",
            };
          } else if (event === "token") {
            yield { type: "token", text: payload.text || "" };
          } else if (event === "done") {
            yield {
              type: "done",
              conversation_id: payload.conversation_id,
              reply: payload.reply || "",
              handoff: Boolean(payload.handoff),
              status: payload.status,
            };
          } else if (event === "error") {
            yield { type: "error", message: payload.message || "Stream error" };
          }
        } catch {
          /* ignore malformed chunk */
        }
      }
    }
  }
}
