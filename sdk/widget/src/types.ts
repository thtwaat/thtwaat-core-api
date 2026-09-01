export type WidgetThemeMode = "light" | "dark" | "auto";
export type WidgetPosition =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";

export interface WidgetTheme {
  mode: WidgetThemeMode;
  primaryColor: string;
  borderRadius: string;
  fontFamily: string;
  avatarUrl?: string | null;
  logoUrl?: string | null;
}

export interface WidgetConfig {
  apiKey: string;
  apiBaseUrl: string;
  theme?: Partial<WidgetTheme>;
  position?: WidgetPosition;
  agentName?: string;
  welcomeMessage?: string;
  suggestedPrompts?: string[];
  zIndex?: number;
  openOnLoad?: boolean;
  user?: Record<string, unknown>;
  locale?: string;
  leadCapture?: boolean;
  enableHandoff?: boolean;
  /**
   * Agent slug — required for voice/image-generation, which call the
   * by-slug endpoints (POST /public/v1/agents/{slug}/voice|image).
   * Text chat and vision (image input) don't need it — they reuse the
   * existing generic /public/v1/chat(/stream) endpoint.
   */
  agentSlug?: string;
  /**
   * Mirror the agent's backend capability flags here (there is no public
   * endpoint that exposes them, so the embedder declares what's enabled —
   * same pattern as the existing `enableHandoff`/`leadCapture` options).
   * All default false/undefined, matching the backend's safe defaults.
   */
  voiceEnabled?: boolean;
  visionEnabled?: boolean;
  imageGenerationEnabled?: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "human";
  content: string;
  createdAt: number;
}

export interface PublicChatUsage {
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  estimated_cost?: number;
  provider?: string | null;
  model?: string | null;
}

export interface PublicChatResponse {
  reply: string;
  conversation_id: string;
  usage?: PublicChatUsage;
  status?: string;
  handoff?: boolean;
  lead?: Record<string, unknown> | null;
}

/** Vision (image input) content block, as accepted by /public/v1/chat(/stream). */
export interface ImageContentBlock {
  type: "image_url";
  image_url: { url: string };
}

export interface PublicVoiceResponse {
  conversation_id: string;
  transcript: string;
  reply: string;
  audio_base64: string;
  audio_mime_type: string;
  usage?: PublicChatUsage;
  status?: string;
  handoff?: boolean;
  lead?: Record<string, unknown> | null;
}

export interface GeneratedImage {
  data_base64: string;
  mime_type: string;
  url?: string | null;
  provider?: string | null;
  model?: string | null;
  revised_prompt?: string | null;
}

export interface PublicImageResponse {
  conversation_id: string;
  images: GeneratedImage[];
  usage?: PublicChatUsage;
  status?: string;
}

export interface WidgetEvents {
  onReady?: (api: THTWAATApi) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onMessage?: (message: ChatMessage) => void;
  onError?: (error: Error) => void;
}

export interface THTWAATApi {
  open: () => void;
  close: () => void;
  toggle: () => void;
  sendMessage: (text: string) => Promise<void>;
  setTheme: (theme: Partial<WidgetTheme> | WidgetThemeMode) => void;
  identifyUser: (user: Record<string, unknown>) => void;
  destroy: () => void;
  isOpen: () => boolean;
}

export interface WidgetRuntimeOptions extends WidgetConfig, WidgetEvents {}

declare global {
  interface Window {
    THTWAAT?: THTWAATApi & {
      init?: (options: WidgetRuntimeOptions) => THTWAATApi;
      version?: string;
    };
  }
}

export {};
