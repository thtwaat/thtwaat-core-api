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
