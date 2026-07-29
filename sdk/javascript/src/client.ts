import { EventBus } from "./events";
import { HttpClient } from "./http";
import { ChatModule } from "./modules/chat";
import { KnowledgeModule } from "./modules/knowledge";
import { AgentModule } from "./modules/agent";
import { WidgetModule } from "./modules/widget";
import { Logger } from "./utils/logger";
import type {
  ChatInput,
  ChatResponse,
  IdentifyPayload,
  SdkEventMap,
  SdkEventName,
  StreamCallbacks,
  THTWAATConfig,
} from "./types";

export const SDK_VERSION = "1.0.0";

function resolveBaseURL(config: THTWAATConfig): string {
  return (config.apiUrl || config.baseURL || "http://localhost:8000").replace(/\/$/, "");
}

function resolveFetch(config: THTWAATConfig): typeof fetch {
  if (config.fetch) return config.fetch.bind(config);
  if (typeof fetch === "undefined") {
    throw new Error(
      "fetch is not available. Pass config.fetch or use Node.js 18+ / a fetch polyfill."
    );
  }
  return fetch.bind(globalThis);
}

export class THTWAAT {
  readonly version = SDK_VERSION;
  readonly chatModule: ChatModule;
  readonly knowledge: KnowledgeModule;
  readonly agent: AgentModule;
  readonly widget: WidgetModule;

  private readonly config: Required<
    Pick<THTWAATConfig, "timeoutMs" | "maxRetries" | "language" | "theme" | "debug">
  > &
    THTWAATConfig;
  private readonly events = new EventBus();
  private readonly http: HttpClient;
  private readonly logger: Logger;
  private agentId?: string;
  private identity: IdentifyPayload = {};

  constructor(config: THTWAATConfig = {}) {
    if (!config.apiKey && !config.bearerToken && !config.sessionToken) {
      throw new Error("Provide apiKey, bearerToken, or sessionToken");
    }

    this.config = {
      timeoutMs: 60_000,
      maxRetries: 2,
      language: "en",
      theme: "light",
      debug: false,
      ...config,
    };

    this.logger = new Logger(Boolean(this.config.debug));
    this.http = new HttpClient({
      baseURL: resolveBaseURL(this.config),
      timeoutMs: this.config.timeoutMs,
      maxRetries: this.config.maxRetries,
      defaultHeaders: {
        "X-THTWAAT-SDK": SDK_VERSION,
        "Accept-Language": this.config.language,
        ...(this.config.headers || {}),
      },
      fetchImpl: resolveFetch(this.config),
      logger: this.logger,
      getAuthHeaders: () => this.authHeaders(),
    });

    this.chatModule = new ChatModule(this.http, this.events, () => this.config.apiKey);
    this.knowledge = new KnowledgeModule(this.http);
    this.agent = new AgentModule(this.http, () => this.agentId);
    this.widget = new WidgetModule();

    queueMicrotask(() => this.events.emit("ready", undefined as void));
  }

  /** Convenience: chat("hi") or chat({ message, sessionId }) */
  chat(input: ChatInput): Promise<ChatResponse> {
    return this.chatModule.chat(input);
  }

  /** Async iterator streaming */
  streamChat(input: ChatInput) {
    return this.chatModule.streamChat(input);
  }

  /** Callback-style streaming */
  streamChatWithCallbacks(input: ChatInput, callbacks?: StreamCallbacks) {
    return this.chatModule.streamChatWithCallbacks(input, callbacks);
  }

  search(params: Parameters<KnowledgeModule["search"]>[0]) {
    return this.knowledge.search(params);
  }

  upload(params: Parameters<KnowledgeModule["upload"]>[0]) {
    return this.knowledge.upload(params);
  }

  history(opts?: Parameters<KnowledgeModule["history"]>[0]) {
    return this.knowledge.history(opts);
  }

  identify(user: IdentifyPayload): this {
    this.identity = { ...this.identity, ...user };
    this.chatModule.identify(this.identity);
    return this;
  }

  setAgentId(agentId: string): this {
    this.agentId = agentId;
    return this;
  }

  setApiKey(apiKey: string): this {
    this.config.apiKey = apiKey;
    return this;
  }

  setBearerToken(token: string): this {
    this.config.bearerToken = token;
    return this;
  }

  setSessionToken(token: string): this {
    this.config.sessionToken = token;
    return this;
  }

  setTheme(theme: string): this {
    this.config.theme = theme;
    try {
      this.widget.setTheme(theme);
    } catch {
      /* widget optional */
    }
    return this;
  }

  on<E extends SdkEventName>(
    event: E,
    handler: (payload: SdkEventMap[E]) => void
  ): () => void {
    return this.events.on(event, handler);
  }

  off<E extends SdkEventName>(
    event: E,
    handler: (payload: SdkEventMap[E]) => void
  ): void {
    this.events.off(event, handler);
  }

  /** Soft reconnect signal for consumers */
  reconnect(): void {
    this.events.emit("reconnect", undefined as void);
  }

  disconnect(): void {
    this.events.emit("disconnect", undefined as void);
    this.events.removeAll();
  }

  getConfig(): Readonly<THTWAATConfig> {
    return { ...this.config };
  }

  private authHeaders(): Record<string, string> {
    if (this.config.bearerToken) {
      return { Authorization: `Bearer ${this.config.bearerToken}` };
    }
    if (this.config.sessionToken) {
      return { Authorization: `Bearer ${this.config.sessionToken}` };
    }
    if (this.config.apiKey) {
      return { Authorization: `Bearer ${this.config.apiKey}` };
    }
    return {};
  }
}

export default THTWAAT;
