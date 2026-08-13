/** Core types for @thtwaat/sdk */

export type AuthMode = "apiKey" | "bearer" | "session";

export interface IdentifyPayload {
  id?: string;
  name?: string;
  email?: string;
  metadata?: Record<string, unknown>;
}

export interface THTWAATConfig {
  apiKey?: string;
  bearerToken?: string;
  sessionToken?: string;
  apiUrl?: string;
  baseURL?: string;
  timeoutMs?: number;
  maxRetries?: number;
  headers?: Record<string, string>;
  language?: string;
  theme?: "light" | "dark" | "auto" | string;
  debug?: boolean;
  fetch?: typeof fetch;
}

export interface ChatRequestObject {
  message: string;
  sessionId?: string | null;
  conversationId?: string | null;
  metadata?: Record<string, unknown>;
  signal?: AbortSignal;
}

export type ChatInput = string | ChatRequestObject;

export interface ChatUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  provider?: string | null;
  model?: string | null;
}

export interface ChatResponse {
  reply: string;
  conversationId: string;
  usage: ChatUsage;
  raw?: unknown;
}

export interface StreamCallbacks {
  onToken?: (text: string) => void;
  onDone?: (result: ChatResponse) => void;
  onError?: (error: Error) => void;
  onTyping?: (typing: boolean) => void;
  /** Server-side progress updates (e.g. "searching knowledge…") before tokens start. */
  onThinking?: (stage: string, message: string) => void;
}

export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "done"; result: ChatResponse }
  | { type: "error"; error: Error }
  /** Emitted before the first token — server-side progress ("understanding", "searching", "generating", etc). Purely informational; safe to ignore. */
  | { type: "thinking"; stage: string; message: string };

export interface SearchParams {
  query: string;
  kbId?: string;
  topK?: number;
  signal?: AbortSignal;
}

export interface SearchResultItem {
  text: string;
  document_name?: string;
  score?: number;
  [key: string]: unknown;
}

export interface SearchResponse {
  results: SearchResultItem[];
  raw?: unknown;
}

export interface UploadParams {
  file: Blob | File | Buffer | ArrayBuffer;
  filename?: string;
  kbId?: string;
  signal?: AbortSignal;
}

export interface AgentInfo {
  id?: string;
  name?: string;
  status?: string;
  widget_id?: string;
  [key: string]: unknown;
}

export type SdkEventMap = {
  ready: void;
  message: ChatResponse;
  typing: boolean;
  stream: StreamEvent;
  error: Error;
  disconnect: void;
  reconnect: void;
};

export type SdkEventName = keyof SdkEventMap;
