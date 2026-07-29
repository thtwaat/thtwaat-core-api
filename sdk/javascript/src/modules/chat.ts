import type { EventBus } from "../events";
import type { HttpClient } from "../http";
import { THTWAATError } from "../errors";
import type {
  ChatInput,
  ChatRequestObject,
  ChatResponse,
  ChatUsage,
  IdentifyPayload,
  StreamCallbacks,
  StreamEvent,
} from "../types";

function normalizeChatInput(input: ChatInput): ChatRequestObject {
  if (typeof input === "string") return { message: input };
  return input;
}

function mapUsage(raw: any): ChatUsage {
  return {
    input_tokens: Number(raw?.input_tokens ?? 0),
    output_tokens: Number(raw?.output_tokens ?? 0),
    total_tokens: Number(raw?.total_tokens ?? 0),
    estimated_cost: Number(raw?.estimated_cost ?? 0),
    provider: raw?.provider ?? null,
    model: raw?.model ?? null,
  };
}

export class ChatModule {
  private sessionId: string | null = null;
  private identity: IdentifyPayload = {};

  constructor(
    private readonly http: HttpClient,
    private readonly events: EventBus,
    private readonly getApiKey: () => string | undefined
  ) {}

  identify(user: IdentifyPayload): void {
    this.identity = { ...this.identity, ...user };
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  setSessionId(id: string | null): void {
    this.sessionId = id;
  }

  async chat(input: ChatInput): Promise<ChatResponse> {
    const req = normalizeChatInput(input);
    const session =
      req.sessionId ?? req.conversationId ?? this.sessionId ?? null;

    this.events.emit("typing", true);
    try {
      const body = {
        api_key: this.getApiKey(),
        message: req.message,
        session_id: session,
        metadata: {
          ...this.identity,
          ...(this.identity.metadata || {}),
          ...(req.metadata || {}),
        },
      };

      const raw = await this.http.request<any>("/public/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: req.signal,
      });

      const result: ChatResponse = {
        reply: String(raw.reply ?? ""),
        conversationId: String(raw.conversation_id ?? ""),
        usage: mapUsage(raw.usage),
        raw,
      };
      if (result.conversationId) this.sessionId = result.conversationId;
      this.events.emit("message", result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      this.events.emit("error", error);
      throw err;
    } finally {
      this.events.emit("typing", false);
    }
  }

  async *streamChat(input: ChatInput): AsyncGenerator<StreamEvent, ChatResponse, void> {
    const req = normalizeChatInput(input);
    const session =
      req.sessionId ?? req.conversationId ?? this.sessionId ?? null;

    this.events.emit("typing", true);
    try {
      const body = {
        api_key: this.getApiKey(),
        message: req.message,
        session_id: session,
        metadata: {
          ...this.identity,
          ...(this.identity.metadata || {}),
          ...(req.metadata || {}),
        },
      };

      let res: Response;
      try {
        res = await this.http.stream("/public/v1/chat/stream", {
          method: "POST",
          body: JSON.stringify(body),
          signal: req.signal,
        });
      } catch (err) {
        // Fallback to non-stream chat
        const result = await this.chat(input);
        const done: StreamEvent = { type: "done", result };
        this.events.emit("stream", done);
        yield done;
        return result;
      }

      if (!res.body) {
        throw new THTWAATError("Streaming body missing", { code: "stream_error" });
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let final: ChatResponse | null = null;
      let assembled = "";

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
          let payload: any;
          try {
            payload = JSON.parse(data);
          } catch {
            continue;
          }

          if (event === "token") {
            const text = String(payload.text || "");
            assembled += text;
            const ev: StreamEvent = { type: "token", text };
            this.events.emit("stream", ev);
            yield ev;
          } else if (event === "done") {
            final = {
              reply: String(payload.reply ?? assembled),
              conversationId: String(payload.conversation_id ?? ""),
              usage: mapUsage(payload.usage),
              raw: payload,
            };
            if (final.conversationId) this.sessionId = final.conversationId;
            const ev: StreamEvent = { type: "done", result: final };
            this.events.emit("stream", ev);
            this.events.emit("message", final);
            yield ev;
          } else if (event === "error") {
            const error = new THTWAATError(payload.message || "Stream error", {
              code: "stream_error",
            });
            const ev: StreamEvent = { type: "error", error };
            this.events.emit("stream", ev);
            this.events.emit("error", error);
            yield ev;
            throw error;
          }
        }
      }

      if (!final) {
        final = {
          reply: assembled,
          conversationId: this.sessionId || "",
          usage: mapUsage({}),
        };
        const ev: StreamEvent = { type: "done", result: final };
        this.events.emit("stream", ev);
        this.events.emit("message", final);
        yield ev;
      }
      return final;
    } finally {
      this.events.emit("typing", false);
    }
  }

  async streamChatWithCallbacks(
    input: ChatInput,
    callbacks: StreamCallbacks = {}
  ): Promise<ChatResponse> {
    callbacks.onTyping?.(true);
    let result: ChatResponse | null = null;
    try {
      for await (const event of this.streamChat(input)) {
        if (event.type === "token") callbacks.onToken?.(event.text);
        if (event.type === "done") {
          result = event.result;
          callbacks.onDone?.(event.result);
        }
        if (event.type === "error") callbacks.onError?.(event.error);
      }
      if (!result) {
        throw new THTWAATError("Stream ended without result", { code: "stream_error" });
      }
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      callbacks.onError?.(error);
      throw err;
    } finally {
      callbacks.onTyping?.(false);
    }
  }
}
