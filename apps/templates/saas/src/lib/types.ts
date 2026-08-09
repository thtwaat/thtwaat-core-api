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
  slug?: string | null;
  description?: string | null;
  system_prompt_template: string;
  provider?: string | null;
  model?: string | null;
  temperature: number;
  status: string;
  version: number;
  is_template: boolean;
  allowed_tools: string[];
  web_config: Record<string, unknown>;
  published_at?: string | null;
  widget_id?: string | null;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentTool = {
  name: string;
  description: string;
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
  company_id: string;
  agent_id: string;
  title?: string | null;
  channel?: string;
  status?: string;
  assigned_to_user_id?: string | null;
  last_read_at?: string | null;
  extra_metadata?: Record<string, unknown>;
  message_count?: number;
  last_message_preview?: string | null;
  last_message_at?: string | null;
  unread?: boolean;
  created_at: string;
  updated_at?: string;
};

export type ConversationMessage = {
  id: string;
  conversation_id: string;
  role: string;
  content?: string | null;
  created_at: string;
};

export type ConversationDetail = Conversation & {
  messages: ConversationMessage[];
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
  allowed_providers?: string[];
  capabilities?: Record<string, string[]>;
  routing_policy?: string;
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

export type AiGatewayDashboard = {
  window_days: number;
  requests: number;
  success: number;
  failed: number;
  success_rate: number;
  tokens: number;
  cost: number;
  currency: string;
  avg_latency_ms: number;
  providers: Array<{
    provider: string;
    requests: number;
    tokens: number;
    cost: number;
    error_rate: number;
    avg_latency_ms: number;
  }>;
  live_routing?: Record<string, unknown>;
  workspace?: AiWorkspaceSettings;
  capabilities?: Record<string, string[]>;
};

export type AiWorkspaceSettings = {
  company_id: string;
  default_provider: string;
  allowed_providers: string[];
  monthly_token_limit?: number | null;
  monthly_request_limit?: number | null;
  monthly_cost_limit_usd?: number | null;
  routing_policy: string;
  retry_max_attempts: number;
  timeout_seconds: number;
  updated_at?: string | null;
};

export type AiGatewayHealthDetail = {
  providers: Record<
    string,
    {
      status: string;
      avg_latency_ms?: number | null;
      last_latency_ms?: number | null;
      capabilities?: string[];
    }
  >;
  success_rate?: number;
  avg_latency_ms?: number;
  cost?: number;
  tokens?: number;
  requests?: number;
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
  yearly_amount?: number | null;
  price_inr?: number | null;
  price_usd?: number | null;
  yearly_price_inr?: number | null;
  yearly_price_usd?: number | null;
  is_custom_pricing?: boolean;
  display_amount?: number | null;
  display_currency?: string | null;
  resolved_provider?: string | null;
  currency?: string;
  interval?: string;
  description?: string;
  features?: string[];
  max_users?: number;
  max_apps?: number;
  max_agents?: number;
  max_messages?: number;
  max_tokens?: number;
  max_storage?: number;
  max_domains?: number;
  max_team_members?: number;
  max_api_keys?: number;
  max_templates?: number;
  max_workspaces?: number;
  max_widgets?: number;
  max_knowledge?: number;
  trial_days?: number;
  ai_credits?: number;
  is_active?: boolean;
};

export type Invoice = {
  id: string;
  number?: string;
  status: string;
  amount?: number;
  amount_paid?: number;
  total?: number;
  currency?: string;
  created_at: string;
  pdf_url?: string;
  invoice_pdf?: string | null;
  hosted_url?: string | null;
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
  display_name?: string | null;
  plan?: string;
  status?: string;
  is_active?: boolean;
  is_verified?: boolean;
  max_users?: number;
  max_apps?: number;
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
