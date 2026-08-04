export type UserProfile = {
  id: string;
  company_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
};

export type MfaChallenge = {
  mfa_required: true;
  mfa_token: string;
  expires_in: number;
};

export type Agent = {
  id: string;
  company_id: string;
  name: string;
  description?: string | null;
  system_prompt_template: string;
  temperature: number;
  status: string;
  version: number;
  is_template: boolean;
  web_config: Record<string, unknown>;
  published_at?: string | null;
  widget_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type PublishResult = {
  api_key?: string;
  widget_id?: string;
  public_chat_url?: string;
  embed_script?: string;
  iframe_url?: string;
  message?: string;
};

export type Conversation = {
  id: string;
  agent_id?: string;
  title?: string;
  created_at: string;
  updated_at?: string;
  message_count?: number;
};

export type KnowledgeBase = {
  id: string;
  name: string;
  description?: string | null;
  document_count?: number;
  created_at: string;
};

export type KnowledgeDocument = {
  id: string;
  name: string;
  status?: string;
  created_at: string;
  size_bytes?: number;
  file_size_bytes?: number;
};

/** AI Gateway provider list — GET /api/v1/ai/providers */
export type AiProvidersList = {
  providers: string[];
  default: string;
};

/** GET /api/v1/ai/health — map of provider → configured | unconfigured | error */
export type AiProviderHealthMap = Record<string, string>;

export type AiProviderModel = {
  id?: string;
  name?: string;
  [key: string]: unknown;
};

export type AiProviderModelsResponse = {
  provider: string;
  models: AiProviderModel[] | string[];
};

export type Domain = {
  id: string;
  hostname: string;
  status: string;
  verification_method: string;
  verification_token: string;
  dns_records: Array<Record<string, unknown>>;
  ssl_status: string;
  ssl_expires_at?: string | null;
  failure_reason?: string | null;
  is_primary: boolean;
  widget_urls?: Record<string, string>;
  created_at: string;
};

export type UsageCurrent = {
  company_id: string;
  plan: string;
  period_start: string;
  period_end: string;
  usage: Record<string, number>;
  limits: Record<string, number>;
  progress: Array<{ dimension: string; current: number; limit: number; percent: number }>;
  upgrade_url?: string;
};

export type Plan = {
  id: string;
  name: string;
  slug?: string;
  price?: number;
  amount?: number;
  currency?: string;
  interval?: string;
  description?: string;
  features?: string[];
  max_agents?: number;
  max_messages?: number;
  max_tokens?: number;
};

export type Invoice = {
  id: string;
  number?: string;
  status: string;
  amount?: number;
  total?: number;
  currency?: string;
  created_at: string;
  pdf_url?: string;
};

export type Subscription = {
  id?: string;
  plan?: string | Plan;
  status?: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
};

export type Company = {
  id: string;
  name: string;
  slug: string;
  plan?: string;
  status?: string;
  brand_color?: string;
  logo_url?: string;
};

export type Webhook = {
  id: string;
  url: string;
  event_types: string[];
  is_active: boolean;
  created_at: string;
  secret?: string | null;
};

export type WebhookDelivery = {
  id: string;
  delivery_id: string;
  webhook_id?: string | null;
  event: string;
  url: string;
  status: string;
  attempts: number;
  last_error?: string | null;
  next_attempt_at?: string | null;
  delivered_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type WebhookDeliveryList = {
  total: number;
  limit: number;
  offset: number;
  results: WebhookDelivery[];
};
