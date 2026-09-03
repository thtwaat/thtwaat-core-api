import { api, ApiError } from "@/lib/api";
import { apiPaths } from "@/lib/config";
import type {
  Agent,
  AgentTool,
  AiProviderHealthMap,
  AiProviderModelsResponse,
  AiProvidersList,
  AiGatewayDashboard,
  AiGatewayHealthDetail,
  AiWorkspaceSettings,
  Company,
  Conversation,
  ConversationDetail,
  Domain,
  Invoice,
  KnowledgeBase,
  KnowledgeDocument,
  Plan,
  PublishResult,
  Subscription,
  UsageCurrent,
  Webhook,
  WebhookDeliveryList
} from "@/lib/types";

export const authApi = {
  forgotPassword: (email: string) =>
    api.v1("/auth/forgot-password", { method: "POST", auth: false, body: { email } }),
  resetPassword: (body: { token: string; new_password: string }) =>
    api.v1("/auth/reset-password", { method: "POST", auth: false, body }),
  googleIdToken: (id_token: string) =>
    api.v1("/auth/google", { method: "POST", auth: false, body: { id_token } }),
  googleStartUrl: () => `${apiPaths.v1}/auth/google/start`
};

export const agentsApi = {
  list: () => api.v2<Agent[]>("/agents"),
  get: (id: string) => api.v2<Agent>(`/agents/${id}`),
  create: (body: Record<string, unknown>) => api.v2<Agent>("/agents", { method: "POST", body }),
  update: (id: string, body: Record<string, unknown>) =>
    api.v2<Agent>(`/agents/${id}`, { method: "PATCH", body }),
  clone: (id: string) => api.v2<Agent>(`/agents/${id}/clone`, { method: "POST" }),
  tools: () => api.v2<AgentTool[]>("/agents/tools"),
  visionCapableModels: () => api.v2<Record<string, string[]>>("/agents/vision-capable-models"),
  chat: (id: string, message: string, conversationId?: string) =>
    api.v2<{ message: string; conversation_id: string; usage: Record<string, unknown> }>(
      `/agents/${id}/chat`,
      { method: "POST", body: { message, conversation_id: conversationId } }
    ),
  deleteImpact: (id: string) => api.v2<AgentDeleteImpact>(`/agents/${id}/delete-impact`),
  delete: (
    id: string,
    body: {
      keep_conversations?: boolean;
      keep_knowledge?: boolean;
      reason?: string;
      confirm_unpublish?: boolean;
    } = {}
  ) =>
    api.v2<{ id: string; status: string; deleted_at: string; retention_days: number; message: string }>(
      `/agents/${id}`,
      { method: "DELETE", body }
    ),
  restore: (id: string, reason?: string) =>
    api.v2<{ id: string; status: string; company_id: string; message: string }>(
      `/admin/agents/${id}/restore`,
      { method: "POST", body: { reason } }
    ),
  publish: (id: string) => api.v1<PublishResult>(`/agents/${id}/publish`, { method: "POST" }),
  unpublish: (id: string) => api.v1(`/agents/${id}/unpublish`, { method: "POST" }),
  pause: (id: string) => api.v1<{ status: string; agent_id: string }>(`/agents/${id}/pause`, { method: "POST" }),
  resume: (id: string) => api.v1<{ status: string; agent_id: string }>(`/agents/${id}/resume`, { method: "POST" }),
  createApiKey: (id: string, name?: string) =>
    api.v1<{ api_key?: string; key?: string; id?: string; plain_key?: string }>(`/agents/${id}/api-keys`, {
      method: "POST",
      body: { name: name || "Default" }
    }),
  embed: (id: string) => api.v1<Record<string, string>>(`/agents/${id}/embed`),
  widget: (id: string) => api.v1<Record<string, unknown>>(`/agents/${id}/widget`),
  updateWidget: (id: string, body: Record<string, unknown>) =>
    api.v1<Record<string, unknown>>(`/agents/${id}/widget`, { method: "PATCH", body })
};

export type AgentDeleteImpact = {
  agent_id: string;
  name: string;
  published: boolean;
  status: string;
  widget: boolean;
  widget_id?: string | null;
  api_keys: number;
  playground: boolean;
  draft_prompts: number;
  scheduled_jobs: number;
  conversations: number;
  knowledge_attachments: number;
  retention_days: number;
};

export const knowledgeApi = {
  listBases: () => api.v2<KnowledgeBase[]>("/knowledge/bases"),
  createBase: (body: { name: string; description?: string }) =>
    api.v2<KnowledgeBase>("/knowledge/bases", { method: "POST", body }),
  listDocuments: (baseId?: string) =>
    api.v2<KnowledgeDocument[]>(
      baseId ? `/knowledge/documents?kb_id=${encodeURIComponent(baseId)}` : "/knowledge/documents"
    ),
  upload: (baseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.v2(`/knowledge/upload?knowledge_base_id=${encodeURIComponent(baseId)}`, {
      method: "POST",
      formData: form
    });
  },
  /** XHR upload with progress events (same endpoint as upload). */
  uploadWithProgress: (
    baseId: string,
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<unknown> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${apiPaths.v2}/knowledge/upload?knowledge_base_id=${encodeURIComponent(baseId)}`;
      xhr.open("POST", url);
      const token = typeof window !== "undefined" ? window.localStorage.getItem("tht_access_token") : null;
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable || !onProgress) return;
        onProgress(Math.round((ev.loaded / ev.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(xhr.responseText ? JSON.parse(xhr.responseText) : {});
          } catch {
            resolve({});
          }
          return;
        }
        let message = `Upload failed (${xhr.status})`;
        try {
          const body = JSON.parse(xhr.responseText);
          message = body?.error || body?.detail || body?.message || message;
          if (typeof body?.detail === "object" && body.detail?.error) message = body.detail.error;
        } catch {
          /* ignore */
        }
        reject(new Error(typeof message === "string" ? message : `Upload failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Upload network error"));
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    });
  },
  deleteDocument: (_baseId: string, docId: string) =>
    api.v2(`/knowledge/documents/${docId}`, { method: "DELETE" }),
  attach: (kbId: string, agentId: string) =>
    api.v2<{ message?: string }>(`/knowledge/bases/${kbId}/agents/${agentId}`, { method: "POST" }),
  detach: (kbId: string, agentId: string) =>
    api.v2<{ message?: string }>(`/knowledge/bases/${kbId}/agents/${agentId}`, { method: "DELETE" }),
  listForAgent: (agentId: string) => api.v2<KnowledgeBase[]>(`/knowledge/agents/${agentId}/bases`),
  search: (baseId: string, q: string) =>
    api.v2<{ results: Array<{ text: string; score?: number; document_name?: string }> }>(
      "/knowledge/search",
      {
        method: "POST",
        body: { query: q, knowledge_base_id: baseId, top_k: 5 }
      }
    )
};

export const domainsApi = {
  list: () => api.v1<Domain[]>("/domains"),
  dashboard: () => api.v1<{ domains?: Domain[] }>("/domains/dashboard"),
  create: (body: Record<string, unknown>) => api.v1<Domain>("/domains", { method: "POST", body }),
  verify: (id: string) => api.v1(`/domains/${id}/verify`, { method: "POST" }),
  retry: (id: string) => api.v1(`/domains/${id}/retry`, { method: "POST" }),
  sslRequest: (id: string) =>
    api.v1<{ message?: string; ssl_status?: string; status?: string; hostname?: string }>(
      `/domains/${id}/ssl/request`,
      { method: "POST" }
    ),
  sslStatus: (id: string) => api.v1(`/domains/${id}/ssl/status`),
  remove: (id: string) => api.v1(`/domains/${id}`, { method: "DELETE" })
};

export const usageApi = {
  current: () => api.v1<UsageCurrent>("/usage/current"),
  dashboard: () => api.v1<Record<string, unknown>>("/usage/dashboard"),
  history: (days = 30) => api.v1<{ points: Array<{ day: string; dimension: string; quantity: number }> }>(`/usage/history?days=${days}`)
};

export const billingApi = {
  plans: (country?: string) => {
    const qs = country ? `?country=${encodeURIComponent(country)}` : "";
    return api.v1<Plan[]>(`/payments/plans/${qs}`);
  },
  plansAdmin: () => api.v1<Plan[]>("/payments/plans/?include_inactive=true"),
  updatePlan: (id: string, body: Record<string, unknown>) =>
    api.v1<Plan>(`/payments/plans/${id}`, { method: "PATCH", body }),
  subscription: () => api.v1<Subscription>("/payments/subscriptions/me"),
  invoices: () => api.v1<Invoice[]>("/payments/invoices"),
  providers: (country?: string) => {
    const qs = country ? `?country=${encodeURIComponent(country)}` : "";
    return api.v1<{
      stripe: { available: boolean; configured: boolean; flag_enabled: boolean };
      razorpay: {
        available: boolean;
        configured: boolean;
        flag_enabled: boolean;
        key_id?: string | null;
      };
      default: string;
      region?: {
        code: string;
        currency: string;
        provider: string;
        country?: string | null;
        country_code?: string | null;
        gateway?: string;
        source?: string;
      };
    }>(`/payments/subscriptions/providers${qs}`);
  },
  billingContext: (country?: string) => {
    const qs = country ? `?country=${encodeURIComponent(country)}` : "";
    return api.v1<{
      country?: string;
      currency: string;
      gateway?: string;
      region: string;
      provider: string;
      country_code?: string | null;
      source?: string;
      providers?: Record<string, unknown>;
    }>(`/payments/subscriptions/billing-context${qs}`);
  },
  setBillingCountry: (country: string) =>
    api.v1<{
      country: string;
      currency: string;
      gateway: string;
      region: string;
      provider: string;
    }>("/payments/subscriptions/billing-country", {
      method: "PUT",
      body: { country }
    }),
  razorpayOrder: (body: {
    plan_id: string;
    customer_name: string;
    customer_email: string;
    customer_phone?: string;
    coupon_code?: string;
    interval?: string;
    country?: string;
  }) =>
    api.v1<{ order_id: string; subscription_id?: string; provider?: string }>(
      "/payments/subscriptions/razorpay/order",
      {
        method: "POST",
        body
      }
    ),
  razorpayVerify: (body: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
    plan_id: string;
  }) =>
    api.v1("/payments/subscriptions/razorpay/verify", {
      method: "POST",
      body
    }),
  stripeCheckout: (body: {
    plan_id: string;
    success_url: string;
    cancel_url: string;
    coupon_code?: string;
    trial_days?: number;
    interval?: string;
    country?: string;
  }) =>
    api.v1<{ checkout_url: string; provider?: string }>("/payments/subscriptions/stripe/checkout", {
      method: "POST",
      body
    }),
  cancel: () => api.v1("/payments/subscriptions/cancel", { method: "POST" }),
  resume: () => api.v1("/payments/subscriptions/resume", { method: "POST" }),
  changePlan: (body: {
    plan_id: string;
    interval?: string;
    coupon_code?: string;
    success_url?: string;
    cancel_url?: string;
    country?: string;
  }) =>
    api.v1<{ checkout_url?: string | null; order_id?: string; provider: string }>(
      "/payments/subscriptions/change-plan",
      { method: "POST", body }
    ),
  validateCoupon: (code: string) =>
    api.v1<{ valid: boolean; percent_off?: number; amount_off?: number; currency: string }>(
      "/payments/coupons/validate",
      { method: "POST", body: { code } }
    ),
  adminAnalytics: () => api.v1<BillingAdminAnalytics>("/payments/admin/analytics")
};

export type BillingAdminAnalytics = {
  mrr: number;
  arr: number;
  revenue: number;
  refunds: number;
  failed_payments: number;
  active_subscriptions: number;
  top_customers: Array<{ company_id: string; revenue: number }>;
  top_plans: Array<{ plan: string; active_subscriptions: number }>;
  token_usage: number;
  ai_costs: number;
  gross_margin: number;
  providers?: {
    stripe?: { available?: boolean };
    razorpay?: { available?: boolean };
  };
};

export const conversationsApi = {
  list: (params?: {
    q?: string;
    agent_id?: string;
    channel?: string;
    status?: string;
    assigned_to?: string;
    unread_only?: boolean;
    skip?: number;
    limit?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    if (params?.agent_id) sp.set("agent_id", params.agent_id);
    if (params?.channel) sp.set("channel", params.channel);
    if (params?.status) sp.set("status", params.status);
    if (params?.assigned_to) sp.set("assigned_to", params.assigned_to);
    if (params?.unread_only) sp.set("unread_only", "true");
    if (params?.skip != null) sp.set("skip", String(params.skip));
    if (params?.limit != null) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return api.v2<Conversation[]>(`/conversations${qs ? `?${qs}` : ""}`);
  },
  create: (body: { agent_id: string; title?: string; channel?: string }) =>
    api.v2<Conversation>("/conversations", { method: "POST", body }),
  get: (id: string, markRead = true) =>
    api.v2<ConversationDetail>(`/conversations/${id}?mark_read=${markRead ? "true" : "false"}`),
  update: (
    id: string,
    body: {
      title?: string;
      status?: string;
      assigned_to_user_id?: string | null;
      clear_assignee?: boolean;
      mark_read?: boolean;
    }
  ) => api.v2<Conversation>(`/conversations/${id}`, { method: "PATCH", body }),
  sendMessage: (
    id: string,
    content: string,
    opts?: { as_human?: boolean; request_handoff?: boolean }
  ) =>
    api.v2<{
      user_message?: unknown;
      assistant_message?: unknown;
      human_message?: unknown;
      status?: string;
    }>(`/conversations/${id}/messages`, {
      method: "POST",
      body: {
        content,
        as_human: opts?.as_human || false,
        request_handoff: opts?.request_handoff || false
      }
    })
};

export const leadsApi = {
  list: (params?: { agent_id?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.agent_id) sp.set("agent_id", params.agent_id);
    if (params?.limit != null) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return api.v2<
      Array<{
        conversation_id: string;
        agent_id: string;
        channel: string;
        status: string;
        lead: Record<string, string>;
        created_at: string;
        updated_at: string;
      }>
    >(`/leads${qs ? `?${qs}` : ""}`);
  }
};

export const companiesApi = {
  get: (id: string) => api.v1<Company>(`/companies/${id}`),
  update: (id: string, body: Record<string, unknown>) =>
    api.v1<Company>(`/companies/${id}`, { method: "PATCH", body }),
  // Trailing slash matches FastAPI route; avoids slash-redirect dropping POST body.
  create: (body: Record<string, unknown>) =>
    api.v1<Company>("/companies/", { method: "POST", auth: false, body }),
  list: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    plan?: string;
    q?: string;
    include_inactive?: boolean;
  }) => {
    const sp = new URLSearchParams();
    if (params?.page != null) sp.set("page", String(params.page));
    if (params?.page_size != null) sp.set("page_size", String(params.page_size));
    if (params?.status) sp.set("status", params.status);
    if (params?.plan) sp.set("plan", params.plan);
    if (params?.q) sp.set("q", params.q);
    if (params?.include_inactive) sp.set("include_inactive", "true");
    const qs = sp.toString();
    return api.v1<{
      total: number;
      page: number;
      page_size: number;
      results: Company[];
    }>(`/companies/${qs ? `?${qs}` : ""}`);
  },
  adminUpdate: (id: string, body: Record<string, unknown>) =>
    api.v1<Company>(`/companies/${id}/admin`, { method: "PATCH", body })
};

export const usersApi = {
  create: (body: Record<string, unknown>) =>
    api.v1("/users/", { method: "POST", auth: false, body }),
  listPage: (params?: {
    company_id?: string;
    page?: number;
    page_size?: number;
    status?: string;
    q?: string;
    include_inactive?: boolean;
    role?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params?.company_id) sp.set("company_id", params.company_id);
    if (params?.page != null) sp.set("page", String(params.page));
    if (params?.page_size != null) sp.set("page_size", String(params.page_size));
    if (params?.status) sp.set("status", params.status);
    if (params?.q) sp.set("q", params.q);
    if (params?.include_inactive) sp.set("include_inactive", "true");
    if (params?.role) sp.set("role", params.role);
    const qs = sp.toString();
    return api.v1<{
      total: number;
      page: number;
      page_size: number;
      results: Array<Record<string, unknown>>;
    }>(`/users/${qs ? `?${qs}` : ""}`);
  },
  list: async () => {
    const page = await usersApi.listPage();
    return page.results ?? [];
  },
  update: (id: string, body: Record<string, unknown>) => api.v1(`/users/${id}`, { method: "PATCH", body }),
  deactivate: (id: string) => api.v1(`/users/${id}`, { method: "DELETE" })
};

export const apiKeysApi = {
  list: () => api.v1<Array<Record<string, unknown>>>("/api-keys"),
  create: (body: { name?: string; app_label?: string; scopes?: string[] }) =>
    api.v1("/api-keys", {
      method: "POST",
      body: {
        name: body.name || "Dashboard key",
        app_label: body.app_label || "saas",
        scopes: body.scopes || []
      }
    }),
  remove: (id: string) => api.v1(`/api-keys/${id}`, { method: "DELETE" })
};

export const webhooksApi = {
  list: () => api.v1<Webhook[]>("/webhooks"),
  create: (body: { url: string; event_types: string[] }) =>
    api.v1<Webhook>("/webhooks", { method: "POST", body }),
  update: (id: string, body: { url?: string; event_types?: string[]; is_active?: boolean }) =>
    api.v1<Webhook>(`/webhooks/${id}`, { method: "PATCH", body }),
  enable: (id: string) => api.v1<Webhook>(`/webhooks/${id}/enable`, { method: "POST" }),
  disable: (id: string) => api.v1<Webhook>(`/webhooks/${id}/disable`, { method: "POST" }),
  remove: (id: string) => api.v1(`/webhooks/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    api.v1<{ status: string; message: string; delivery_id?: string }>(`/webhooks/${id}/test`, {
      method: "POST"
    }),
  secret: (id: string) => api.v1<{ id: string; secret: string }>(`/webhooks/${id}/secret`),
  deliveries: (params?: {
    webhook_id?: string;
    status?: string;
    event?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.webhook_id) qs.set("webhook_id", params.webhook_id);
    if (params?.status) qs.set("status", params.status);
    if (params?.event) qs.set("event", params.event);
    if (params?.q) qs.set("q", params.q);
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs}` : "";
    return api.v1<WebhookDeliveryList>(`/webhooks/deliveries${suffix}`);
  },
  retryDelivery: (deliveryId: string) =>
    api.v1<{ status: string; message: string; delivery_id: string }>(
      `/webhooks/deliveries/${encodeURIComponent(deliveryId)}/retry`,
      { method: "POST" }
    )
};

export type TemplateCategory = {
  slug: string;
  name: string;
  count: number;
  icon?: string | null;
  template_count?: number | null;
  popularity_score?: number;
  is_featured?: boolean;
  description?: string | null;
};

export type TemplateItem = {
  id: string;
  slug: string;
  name: string;
  category: string;
  kind?: string;
  pricing_tier?: string;
  industry?: string | null;
  description: string;
  version: string;
  thumbnail?: string | null;
  icon?: string | null;
  tags: string[];
  author: string;
  status: string;
  price: string;
  is_public: boolean;
  is_featured: boolean;
  supports_agents: boolean;
  supports_domains: boolean;
  supports_billing: boolean;
  supports_mobile: boolean;
  package_path?: string | null;
  install_count: number;
  default_config?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  installed: boolean;
  update_available: boolean;
  is_favorited?: boolean;
  banner_url?: string | null;
  screenshots?: string[];
  video_url?: string | null;
  live_demo_url?: string | null;
  verified_publisher?: boolean | null;
  publisher_slug?: string | null;
  company_name?: string | null;
  discount_percent?: number | null;
  rating_avg?: number | null;
  review_count?: number | null;
  download_count?: number | null;
  estimated_install_minutes?: number | null;
  compatibility?: string | null;
  is_editors_choice?: boolean;
  pricing_badge?: string | null;
  listing_id?: string | null;
  what_it_does?: string | null;
  best_for?: string[];
  use_cases?: string[];
  industries?: string[];
  languages?: string[];
  license?: string | null;
  permissions?: string[];
  feature_cards?: Array<{ key: string; title: string; description: string }>;
  docs_markdown?: string | null;
  quick_start?: string | null;
  installation_docs?: string | null;
  configuration_docs?: string | null;
  examples_docs?: string | null;
  support_url?: string | null;
  website_url?: string | null;
  docs_url?: string | null;
  min_platform_version?: string | null;
  supported_providers?: string[];
  dependencies?: string[];
  publisher_bio?: string | null;
  publisher_website?: string | null;
};

export type TemplateVersion = {
  id: string;
  template_id: string;
  version: string;
  changelog?: string | null;
  release_notes?: string | null;
  config?: Record<string, unknown>;
  is_latest: boolean;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type TemplateReviewItem = {
  id: string;
  listing_id: string;
  company_id: string;
  user_id: string;
  rating: number;
  title?: string | null;
  body?: string | null;
  created_at: string;
  verified_install?: boolean;
  helpful_count?: number;
};

export type TemplateReviewsPayload = {
  template_id: string;
  listing_id?: string | null;
  rating_avg?: number | null;
  review_count: number;
  distribution: Record<string, number>;
  items: TemplateReviewItem[];
};

export type Installation = {
  id: string;
  template_id: string;
  template_slug?: string | null;
  template_name?: string | null;
  category?: string | null;
  installed_version: string;
  previous_version?: string | null;
  status: string;
  agent_id?: string | null;
  api_key?: string | null;
  api_key_prefix?: string | null;
  domain_id?: string | null;
  published_at?: string | null;
  update_available: boolean;
  latest_available_version?: string | null;
  failure_reason?: string | null;
  created_at: string;
};

export type UpdateNotification = {
  installation_id: string;
  template_id: string;
  template_slug: string;
  template_name: string;
  installed_version: string;
  latest_version: string;
  changelog?: string | null;
};

export type MarketplaceCollection = {
  id: string;
  slug: string;
  name: string;
  description: string;
  icon?: string | null;
  banner_url?: string | null;
  is_featured: boolean;
  sort_order: number;
  collection_type: string;
  item_count: number;
  items?: TemplateItem[];
  computed_rule?: Record<string, unknown>;
};

export type MarketplaceHome = {
  featured: TemplateItem[];
  newest: TemplateItem[];
  trending: TemplateItem[];
  top_rated: TemplateItem[];
  most_installed: TemplateItem[];
  editors_choice: TemplateItem[];
  continue_using: TemplateItem[];
  recently_installed: TemplateItem[];
  recently_viewed: TemplateItem[];
  categories: TemplateCategory[];
  collections: MarketplaceCollection[];
  installed_count: number;
  updates_count: number;
};

export type MarketplaceDashboard = {
  featured: TemplateItem[];
  newest: TemplateItem[];
  installed_count: number;
  updates_count: number;
  categories: TemplateCategory[];
};

export const marketplaceApi = {
  home: () => api.v1<MarketplaceHome>("/marketplace/home"),
  dashboard: () => api.v1<MarketplaceDashboard>("/marketplace/dashboard"),
  categories: () => api.v1<TemplateCategory[]>("/marketplace/categories"),
  collections: () => api.v1<MarketplaceCollection[]>("/marketplace/collections"),
  collection: (slug: string) =>
    api.v1<MarketplaceCollection>(`/marketplace/collections/${encodeURIComponent(slug)}`),
  list: async (params?: {
    q?: string;
    category?: string;
    featured?: boolean;
    newest?: boolean;
    kind?: string;
    pricing_tier?: string;
    sort?: string;
    limit?: number;
    offset?: number;
  }) => {
    const page = await marketplaceApi.listPage(params);
    return page.items;
  },
  listPage: (params?: {
    q?: string;
    category?: string;
    featured?: boolean;
    newest?: boolean;
    kind?: string;
    pricing_tier?: string;
    sort?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.category) qs.set("category", params.category);
    if (params?.featured != null) qs.set("featured", String(params.featured));
    if (params?.newest) qs.set("newest", "true");
    if (params?.kind) qs.set("kind", params.kind);
    if (params?.pricing_tier) qs.set("pricing_tier", params.pricing_tier);
    if (params?.sort) qs.set("sort", params.sort);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    return api.v1<{ items: TemplateItem[]; total: number; limit: number; offset: number; sort: string }>(
      `/marketplace/templates${qs.size ? `?${qs}` : ""}`
    );
  },
  adminList: (params?: {
    q?: string;
    category?: string;
    kind?: string;
    pricing_tier?: string;
    status?: string;
    sort?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.category) qs.set("category", params.category);
    if (params?.kind) qs.set("kind", params.kind);
    if (params?.pricing_tier) qs.set("pricing_tier", params.pricing_tier);
    if (params?.status) qs.set("status", params.status);
    if (params?.sort) qs.set("sort", params.sort);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    return api.v1<{ items: TemplateItem[]; total: number; limit: number; offset: number; sort: string }>(
      `/marketplace/admin/templates${qs.size ? `?${qs}` : ""}`
    );
  },
  createTemplate: (body: Record<string, unknown>) =>
    api.v1<TemplateItem>("/marketplace/templates", { method: "POST", body }),
  updateTemplate: (id: string, body: Record<string, unknown>) =>
    api.v1<TemplateItem>(`/marketplace/templates/${id}`, { method: "PUT", body }),
  archiveTemplate: (id: string) =>
    api.v1<TemplateItem>(`/marketplace/templates/${id}`, { method: "DELETE" }),
  publishTemplate: (id: string) =>
    api.v1<TemplateItem>(`/marketplace/templates/${id}/publish`, { method: "POST" }),
  addVersion: (
    id: string,
    body: {
      version: string;
      changelog?: string;
      release_notes?: string;
      config?: Record<string, unknown>;
      set_latest?: boolean;
    }
  ) => api.v1<TemplateVersion>(`/marketplace/templates/${id}/versions`, { method: "POST", body }),
  updateVersion: (
    idOrSlug: string,
    versionRef: string,
    body: {
      changelog?: string;
      release_notes?: string;
      config?: Record<string, unknown>;
      set_latest?: boolean;
    }
  ) =>
    api.v1<TemplateVersion>(
      `/marketplace/templates/${encodeURIComponent(idOrSlug)}/versions/${encodeURIComponent(versionRef)}`,
      { method: "PATCH", body }
    ),
  promoteVersion: (idOrSlug: string, versionRef: string) =>
    api.v1<TemplateVersion>(
      `/marketplace/templates/${encodeURIComponent(idOrSlug)}/versions/${encodeURIComponent(versionRef)}/promote`,
      { method: "POST" }
    ),
  get: (idOrSlug: string) => api.v1<TemplateItem>(`/marketplace/templates/${idOrSlug}`),
  reviews: (idOrSlug: string, limit = 50) =>
    api.v1<TemplateReviewsPayload>(
      `/marketplace/templates/${encodeURIComponent(idOrSlug)}/reviews?limit=${limit}`
    ),
  versions: (idOrSlug: string) =>
    api.v1<TemplateVersion[]>(`/marketplace/templates/${encodeURIComponent(idOrSlug)}/versions`),
  getVersion: (idOrSlug: string, versionRef: string) =>
    api.v1<TemplateVersion>(
      `/marketplace/templates/${encodeURIComponent(idOrSlug)}/versions/${encodeURIComponent(versionRef)}`
    ),
  favorites: () => api.v1<TemplateItem[]>("/marketplace/favorites"),
  favorite: (idOrSlug: string) =>
    api.v1<TemplateItem>(`/marketplace/templates/${encodeURIComponent(idOrSlug)}/favorite`, {
      method: "POST"
    }),
  unfavorite: (idOrSlug: string) =>
    api.v1(`/marketplace/templates/${encodeURIComponent(idOrSlug)}/favorite`, { method: "DELETE" }),
  installed: () => api.v1<Installation[]>("/marketplace/installed"),
  updates: () => api.v1<UpdateNotification[]>("/marketplace/updates"),
  install: (
    idOrSlug: string,
    body?: { create_api_key?: boolean; config_overrides?: Record<string, unknown>; agent_id?: string }
  ) =>
    api.v1<Installation>(`/marketplace/templates/${encodeURIComponent(idOrSlug)}/install`, {
      method: "POST",
      body: body || { create_api_key: false }
    }),
  connect: (installId: string, body: { agent_id?: string; create_api_key?: boolean; domain_id?: string }) =>
    api.v1<Installation>(`/marketplace/installations/${installId}/connect`, { method: "POST", body }),
  publish: (installId: string) =>
    api.v1<Installation>(`/marketplace/installations/${installId}/publish`, { method: "POST" }),
  update: (installId: string, version?: string) =>
    api.v1<Installation>(`/marketplace/installations/${installId}/update${version ? `?version=${version}` : ""}`, {
      method: "POST"
    }),
  rollback: (installId: string) =>
    api.v1<Installation>(`/marketplace/installations/${installId}/rollback`, { method: "POST" }),
  uninstall: (installId: string) =>
    api.v1(`/marketplace/installations/${installId}`, { method: "DELETE" }),
  analytics: (days = 30) =>
    api.v1<MarketplaceAnalytics>(`/marketplace/analytics?days=${days}`),
  adminAnalytics: (days = 30) =>
    api.v1<MarketplaceAnalytics>(`/marketplace/admin/analytics?days=${days}`)
};

export type AnalyticsCountItem = { key: string; label: string; count: number };
export type AnalyticsDayPoint = { day: string; installs: number };
export type AnalyticsTemplateRank = {
  template_id: string;
  slug: string;
  name: string;
  kind: string;
  category: string;
  install_count: number;
  status?: string | null;
};

export type MarketplaceAnalytics = {
  days: number;
  company: {
    installed_count: number;
    updates_available: number;
    favorites_count: number;
    by_status: AnalyticsCountItem[];
    by_category: AnalyticsCountItem[];
    by_kind: AnalyticsCountItem[];
    installs_over_time: AnalyticsDayPoint[];
    recent_installs: AnalyticsTemplateRank[];
  };
  catalog?: {
    templates_total: number;
    published: number;
    draft: number;
    archived: number;
    favorites_total: number;
    active_installs: number;
    by_kind: AnalyticsCountItem[];
    by_category: AnalyticsCountItem[];
    by_pricing_tier: AnalyticsCountItem[];
    top_templates: AnalyticsTemplateRank[];
    installs_over_time: AnalyticsDayPoint[];
  } | null;
};

// ── Agent Store (admin + storefront hooks) ────────────────────────────────────

export type StoreAdminStats = {
  listings_total: number;
  pending_review: number;
  published: number;
  suspended: number;
  open_abuse_reports: number;
  purchases_completed: number;
  gross_gmv: number;
};

export type AgentListing = {
  id: string;
  slug: string;
  title: string;
  short_description: string;
  long_description?: string;
  screenshots?: string[];
  demo_url?: string | null;
  cover_url?: string | null;
  logo_url?: string | null;
  supported_languages?: string[];
  knowledge_requirements?: string | null;
  categories?: string[];
  tags?: string[];
  status: string;
  is_featured: boolean;
  is_verified_badge: boolean;
  publisher_id?: string;
  publisher_name?: string | null;
  publisher_verified?: boolean;
  pricing_model: string;
  price_amount: string | number;
  currency?: string;
  current_version: string;
  release_notes?: string | null;
  install_count: number;
  download_count?: number;
  rating_avg?: string | number;
  rating_count?: number;
  published_at?: string | null;
  created_at: string;
  updated_at?: string;
};

export type AbuseReport = {
  id: string;
  listing_id: string;
  reason: string;
  details?: string | null;
  status: string;
  created_at: string;
};

export type PublisherProfile = {
  id: string;
  company_id: string;
  display_name: string;
  slug: string;
  bio?: string | null;
  website?: string | null;
  logo_url?: string | null;
  banner_url?: string | null;
  github_url?: string | null;
  linkedin_url?: string | null;
  twitter_url?: string | null;
  followers_count?: number;
  following_count?: number;
  is_verified: boolean;
  status: string;
  revenue_share_bps: number;
  created_at: string;
};

export type PublisherPublicProfile = {
  id: string;
  display_name: string;
  slug: string;
  bio?: string | null;
  website?: string | null;
  logo_url?: string | null;
  banner_url?: string | null;
  github_url?: string | null;
  linkedin_url?: string | null;
  twitter_url?: string | null;
  is_verified: boolean;
  followers_count: number;
  following_count: number;
  templates_count: number;
  published_count: number;
  average_rating: number;
  total_installs: number;
  listings: AgentListing[];
};

export type PublisherAnalytics = {
  listings: number;
  published_listings: number;
  draft_listings?: number;
  pending_review_listings?: number;
  private_listings?: number;
  rejected_listings?: number;
  archived_listings?: number;
  total_installs: number;
  active_installs?: number;
  total_downloads: number;
  average_rating: number;
  review_count: number;
  completed_purchases: number;
  gross_revenue: number;
  publisher_revenue: number;
  platform_fees: number;
  monthly_growth_pct?: number;
  currency: string;
  daily_installs?: Array<{ date: string; count: number }>;
  monthly_installs?: Array<{ month: string; count: number }>;
  countries?: Array<{ country: string; count: number }>;
  devices?: Array<{ device: string; count: number }>;
  conversion_rate?: number;
  retention_rate?: number;
};

export type AgentStoreReview = {
  id: string;
  listing_id: string;
  company_id: string;
  user_id: string;
  rating: number;
  title?: string | null;
  body?: string | null;
  publisher_reply?: string | null;
  publisher_replied_at?: string | null;
  helpful_count?: number;
  created_at: string;
};

export type ListingCreateBody = {
  title: string;
  slug: string;
  short_description?: string;
  long_description?: string;
  screenshots?: string[];
  demo_url?: string | null;
  cover_url?: string | null;
  logo_url?: string | null;
  supported_languages?: string[];
  knowledge_requirements?: string | null;
  categories?: string[];
  tags?: string[];
  pricing_model?: string;
  price_amount?: number | string;
  currency?: string;
  pricing_tier?: string | null;
  marketplace_category?: string;
  default_config?: Record<string, unknown>;
  version?: string;
  release_notes?: string | null;
  submit_for_review?: boolean;
  as_private?: boolean;
};

export const agentStoreApi = {
  adminStats: () => api.v1<StoreAdminStats>("/agent-store/admin/stats"),
  pending: (limit = 50) =>
    api.v1<AgentListing[]>(`/agent-store/admin/pending?limit=${limit}`),
  moderate: (listingId: string, body: { action: string; notes?: string }) =>
    api.v1<AgentListing>(`/agent-store/admin/listings/${listingId}/moderate`, {
      method: "POST",
      body
    }),
  abuseReports: (params?: { status?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.limit) qs.set("limit", String(params.limit));
    return api.v1<AbuseReport[]>(`/agent-store/admin/abuse-reports${qs.size ? `?${qs}` : ""}`);
  },
  resolveAbuse: (reportId: string, body: { status: string; resolution_notes?: string }) =>
    api.v1<AbuseReport>(`/agent-store/admin/abuse-reports/${reportId}/resolve`, {
      method: "POST",
      body
    }),

  // Publisher portal
  getMe: () => api.v1<PublisherProfile>("/agent-store/publisher/me"),
  upsertMe: (body: {
    display_name: string;
    slug: string;
    bio?: string | null;
    website?: string | null;
    logo_url?: string | null;
    banner_url?: string | null;
    github_url?: string | null;
    linkedin_url?: string | null;
    twitter_url?: string | null;
  }) => api.v1<PublisherProfile>("/agent-store/publisher/me", { method: "PUT", body }),
  myListings: () => api.v1<AgentListing[]>("/agent-store/publisher/listings"),
  createListing: (body: ListingCreateBody) =>
    api.v1<AgentListing>("/agent-store/publisher/listings", { method: "POST", body }),
  updateListing: (id: string, body: Partial<ListingCreateBody>) =>
    api.v1<AgentListing>(`/agent-store/publisher/listings/${id}`, { method: "PATCH", body }),
  submitListing: (id: string) =>
    api.v1<AgentListing>(`/agent-store/publisher/listings/${id}/submit`, { method: "POST" }),
  duplicateListing: (id: string) =>
    api.v1<AgentListing>(`/agent-store/publisher/listings/${id}/duplicate`, { method: "POST" }),
  setListingStatus: (id: string, status: string) =>
    api.v1<AgentListing>(`/agent-store/publisher/listings/${id}/status`, {
      method: "POST",
      body: { status }
    }),
  archiveListing: (id: string) =>
    api.v1<AgentListing>(`/agent-store/publisher/listings/${id}`, { method: "DELETE" }),
  analytics: () => api.v1<PublisherAnalytics>("/agent-store/publisher/analytics"),
  reviews: () => api.v1<AgentStoreReview[]>("/agent-store/publisher/reviews"),
  replyReview: (reviewId: string, reply: string) =>
    api.v1<AgentStoreReview>(`/agent-store/publisher/reviews/${reviewId}/reply`, {
      method: "POST",
      body: { reply }
    }),
  aiGenerate: (body: {
    kind: string;
    title: string;
    short_description?: string;
    long_description?: string;
    categories?: string[];
    tags?: string[];
    language?: string;
  }) =>
    api.v1<{ kind: string; result: string; tags: string[] }>("/agent-store/publisher/ai/generate", {
      method: "POST",
      body
    }),
  publicPublisher: (slug: string) =>
    api.v1<PublisherPublicProfile>(`/agent-store/publishers/${slug}`),
  markReviewHelpful: (reviewId: string) =>
    api.v1<AgentStoreReview>(`/agent-store/reviews/${reviewId}/helpful`, { method: "POST" }),
  reportAbuse: (listingId: string, body: { reason: string; details?: string }) =>
    api.v1<AbuseReport>(`/agent-store/listings/${listingId}/abuse-reports`, {
      method: "POST",
      body
    })
};

// ── Product Generator ─────────────────────────────────────────────────────────

export type AnalysisResult = {
  industry: string;
  product_type: string;
  category: string;
  required_features: string[];
  brand_tone: string;
  language: string;
  suggested_name: string;
  confidence: number;
  keywords_matched: string[];
  recommended_template_slug?: string | null;
  recommended_template_name?: string | null;
};

export type ProductGeneration = {
  id: string;
  company_id: string;
  prompt: string;
  status: string;
  analysis: Record<string, unknown>;
  template_id?: string | null;
  template_slug?: string | null;
  installation_id?: string | null;
  agent_id?: string | null;
  knowledge_base_id?: string | null;
  api_key_id?: string | null;
  api_key_prefix?: string | null;
  api_key?: string | null;
  widget_id?: string | null;
  domain_id?: string | null;
  product_config: Record<string, unknown>;
  preview_url?: string | null;
  widget_snippet?: string | null;
  publish_status?: string | null;
  deployment_checklist: Array<{ key: string; label: string; done: boolean; href?: string | null }>;
  result: Record<string, unknown>;
  failure_reason?: string | null;
  already_installed?: boolean;
  reuse_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductOutput = {
  generation_id: string;
  preview_url?: string | null;
  publish_status: string;
  widget?: Record<string, unknown> | null;
  api_key?: string | null;
  deployment_checklist: Array<{ key: string; label: string; done: boolean; href?: string | null }>;
  agent_id?: string | null;
  template_slug?: string | null;
  installation_id?: string | null;
};

export const productGeneratorApi = {
  analyze: (prompt: string) =>
    api.v1<AnalysisResult>("/product-generator/analyze", {
      method: "POST",
      body: { prompt }
    }),
  generate: (body: {
    prompt: string;
    template_slug?: string;
    config_overrides?: Record<string, unknown>;
    create_domain_hostname?: string;
    auto_publish?: boolean;
  }) => api.v1<ProductGeneration>("/product-generator/generate", { method: "POST", body }),
  list: () => api.v1<ProductGeneration[]>("/product-generator/generations"),
  get: (id: string) => api.v1<ProductGeneration>(`/product-generator/generations/${id}`),
  output: (id: string) => api.v1<ProductOutput>(`/product-generator/generations/${id}/output`),
  publish: (id: string, hostname?: string) =>
    api.v1<ProductGeneration>(`/product-generator/generations/${id}/publish`, {
      method: "POST",
      body: { hostname: hostname || null }
    })
};

/** THTWAAT Studio — prompt workspace + AI Product Architect. */
export const studioApi = {
  list: (limit = 50, offset = 0) =>
    api.apiV2<import("@/lib/studio").StudioProjectList>(
      `/studio/projects?limit=${limit}&offset=${offset}`
    ),
  get: (id: string) => api.apiV2<import("@/lib/studio").StudioProject>(`/studio/projects/${id}`),
  create: (body: { prompt: string; title?: string }) =>
    api.apiV2<import("@/lib/studio").StudioProject>("/studio/projects", {
      method: "POST",
      body
    }),
  remove: (id: string) => api.apiV2<void>(`/studio/projects/${id}`, { method: "DELETE" }),
  analyze: (id: string, useAi = true) =>
    api.apiV2<import("@/lib/studio").StudioAnalyzeResult>(
      `/studio/projects/${id}/analyze?use_ai=${useAi ? "true" : "false"}`,
      { method: "POST" }
    ),
  getBlueprint: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioBlueprint>(`/studio/projects/${id}/blueprint`),
  saveBlueprint: (id: string, blueprint: import("@/lib/studio").ProductBlueprint) =>
    api.apiV2<import("@/lib/studio").StudioBlueprint>(`/studio/projects/${id}/blueprint`, {
      method: "PUT",
      body: { blueprint }
    }),
  versions: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioBlueprintVersionList>(
      `/studio/projects/${id}/versions`
    ),
  restore: (id: string, version: number) =>
    api.apiV2<import("@/lib/studio").StudioBlueprint>(
      `/studio/projects/${id}/restore/${version}`,
      { method: "POST" }
    ),
  compose: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioComposeResult>(`/studio/projects/${id}/compose`, {
      method: "POST"
    }),
  getBuildPlan: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioBuildPlan>(`/studio/projects/${id}/build-plan`),
  generateFrontend: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioFrontendGenerateResult>(
      `/studio/projects/${id}/generate/frontend`,
      { method: "POST" }
    ),
  getFrontend: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioFrontend>(`/studio/projects/${id}/frontend`),
  saveFrontend: (
    id: string,
    body: { manifest: import("@/lib/studio").FrontendManifest; status?: string }
  ) =>
    api.apiV2<import("@/lib/studio").StudioFrontend>(`/studio/projects/${id}/frontend`, {
      method: "PUT",
      body
    }),
  generateBackend: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioBackendGenerateResult>(
      `/studio/projects/${id}/generate/backend`,
      { method: "POST" }
    ),
  getBackend: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioBackend>(`/studio/projects/${id}/backend`),
  saveBackend: (
    id: string,
    body: { manifest: import("@/lib/studio").BackendManifest; status?: string }
  ) =>
    api.apiV2<import("@/lib/studio").StudioBackend>(`/studio/projects/${id}/backend`, {
      method: "PUT",
      body
    }),
  generateAi: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioAiGenerateResult>(`/studio/projects/${id}/generate/ai`, {
      method: "POST"
    }),
  getAi: (id: string) => api.apiV2<import("@/lib/studio").StudioAi>(`/studio/projects/${id}/ai`),
  saveAi: (id: string, body: { manifest: import("@/lib/studio").AiManifest; status?: string }) =>
    api.apiV2<import("@/lib/studio").StudioAi>(`/studio/projects/${id}/ai`, {
      method: "PUT",
      body
    }),
  generateInfrastructure: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioInfrastructureGenerateResult>(
      `/studio/projects/${id}/generate/infrastructure`,
      { method: "POST" }
    ),
  getInfrastructure: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioInfrastructure>(`/studio/projects/${id}/infrastructure`),
  saveInfrastructure: (
    id: string,
    body: { manifest: import("@/lib/studio").InfraManifest; status?: string }
  ) =>
    api.apiV2<import("@/lib/studio").StudioInfrastructure>(`/studio/projects/${id}/infrastructure`, {
      method: "PUT",
      body
    }),
  getReview: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioReviewResult>(`/studio/projects/${id}/review`),
  approveBuild: (id: string, body?: { notes?: string }) =>
    api.apiV2<import("@/lib/studio").StudioApproveResult>(`/studio/projects/${id}/approve`, {
      method: "POST",
      body: body || {}
    }),
  exportProject: (
    id: string,
    body: { kind?: string; format?: string }
  ) =>
    api.apiV2<import("@/lib/studio").StudioExportResult>(`/studio/projects/${id}/export`, {
      method: "POST",
      body: { kind: body.kind || "review", format: body.format || "json" }
    }),
  generateSource: (id: string, body?: { sync?: boolean; notes?: string }) =>
    api.apiV2<import("@/lib/studio").StudioGenerateSourceResult>(
      `/studio/projects/${id}/generate/source`,
      { method: "POST", body: body || {} }
    ),
  getBuild: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioBuild>(`/studio/projects/${id}/build`),
  getArtifacts: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioArtifacts>(`/studio/projects/${id}/artifacts`),
  retryBuild: (id: string, body?: { sync?: boolean; notes?: string }) =>
    api.apiV2<import("@/lib/studio").StudioGenerateSourceResult>(`/studio/projects/${id}/retry`, {
      method: "POST",
      body: body || {}
    }),
  downloadArtifactsUrl: (id: string) => `/api/v2/studio/projects/${id}/artifacts/download`,
  deploy: (
    id: string,
    body?: {
      provider?: string;
      domain?: string;
      subdomain?: string;
      domain_mode?: "free_subdomain" | "custom";
      environment?: string;
      sync?: boolean;
      notes?: string;
    }
  ) =>
    api.apiV2<import("@/lib/studio").StudioDeployStartResult>(`/studio/projects/${id}/deploy`, {
      method: "POST",
      body: body || { provider: "vps", domain_mode: "free_subdomain", sync: true }
    }),
  listDeployments: (id: string) =>
    api.apiV2<import("@/lib/studio").StudioDeploymentList>(`/studio/projects/${id}/deployments`),
  getDeployment: (id: string, deploymentId: string) =>
    api.apiV2<import("@/lib/studio").StudioDeployment>(
      `/studio/projects/${id}/deployments/${deploymentId}`
    ),
  deploymentStreamUrl: (id: string, deploymentId: string) =>
    `/api/v2/studio/projects/${id}/deployments/${deploymentId}/stream`,
  rollback: (id: string, body?: { deployment_id?: string; sync?: boolean }) =>
    api.apiV2<import("@/lib/studio").StudioRollbackResult>(`/studio/projects/${id}/rollback`, {
      method: "POST",
      body: body || { sync: true }
    }),
  launchChecklist: (id: string) =>
    api.apiV2<{
      ready: boolean;
      passed: number;
      total: number;
      items: Array<{
        key: string;
        title: string;
        ok: boolean;
        required?: boolean;
        detail?: string;
        href?: string;
      }>;
      checked_at: string;
    }>(`/studio/projects/${id}/launch-checklist`),
  launchDiagnostics: (id: string) =>
    api.apiV2<{
      overall: string;
      failed: number;
      warnings: number;
      components: Array<{
        key: string;
        title: string;
        status: string;
        detail?: Record<string, unknown>;
      }>;
      checked_at: string;
    }>(`/studio/projects/${id}/launch-diagnostics`),
  domainWizard: (id: string, hostname: string, auto_verify = true) =>
    api.apiV2<{
      hostname: string;
      domain_id?: string;
      phase: string;
      phase_label: string;
      dns_reachable: boolean;
      dns_verified: boolean;
      domain_status: string;
      ssl_status: string;
      dns_records: Array<Record<string, unknown>>;
      poll_interval_seconds: number;
      checked_at: string;
      error?: string;
    }>(`/studio/projects/${id}/domain-wizard?hostname=${encodeURIComponent(hostname)}`),
  startDomainWizard: (id: string, body: { hostname: string; auto_verify?: boolean }) =>
    api.apiV2<{
      hostname: string;
      phase: string;
      phase_label: string;
      dns_records: Array<Record<string, unknown>>;
      poll_interval_seconds: number;
    }>(`/studio/projects/${id}/domain-wizard`, { method: "POST", body })
};

/** AI Gateway provider status — enterprise dashboard surface */
export const aiProvidersApi = {
  list: () => api.v1<AiProvidersList>("/ai/providers"),
  health: () => api.v1<AiProviderHealthMap>("/ai/health"),
  healthDetail: () => api.v1<AiGatewayHealthDetail>("/ai/gateway/health-detail"),
  dashboard: () => api.v1<AiGatewayDashboard>("/ai/gateway/dashboard"),
  workspaceSettings: () => api.v1<AiWorkspaceSettings>("/ai/workspace-settings"),
  updateWorkspaceSettings: (body: Partial<AiWorkspaceSettings>) =>
    api.v1<AiWorkspaceSettings>("/ai/workspace-settings", { method: "PUT", body }),
  models: (provider: string) =>
    api.v1<AiProviderModelsResponse>(`/ai/models?provider=${encodeURIComponent(provider)}`)
};

/** Customer onboarding facade — delegates to existing platform services */
export type OnboardingSession = {
  id: string;
  resume_token: string;
  user_id: string;
  company_id: string;
  status: "in_progress" | "paused" | "completed" | "abandoned";
  current_step: string;
  completed_steps: string[];
  skipped_steps: string[];
  draft_data: Record<string, unknown>;
  resource_ids: Record<string, unknown>;
  checklist: Array<{
    step: string;
    title: string;
    optional: boolean;
    status: string;
    estimated_minutes: number;
    integration: string;
  }>;
  progress: {
    current_step: string;
    current_order: number;
    total_steps: number;
    completed_count: number;
    skipped_count: number;
    percent_complete: number;
    estimated_minutes_total: number;
    estimated_minutes_remaining: number;
    status: string;
  };
  started_at: string;
  last_active_at: string;
  paused_at?: string | null;
  completed_at?: string | null;
  last_error?: string | null;
};

export type OnboardingStepAction = {
  session: OnboardingSession;
  result: Record<string, unknown>;
  next_step?: string | null;
};

export type StartOnboardingResponse = {
  session: OnboardingSession;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  next_actions: string[];
};

export const onboardingApi = {
  flow: () =>
    api.v1<{
      steps: Array<Record<string, unknown>>;
      total_estimated_minutes: number;
      optional_steps: string[];
      integrations: string[];
    }>("/onboarding/flow", { auth: false }),
  start: (body: {
    account: {
      email: string;
      password: string;
      first_name: string;
      last_name: string;
    };
    company: {
      name: string;
      slug?: string;
      display_name?: string;
      industry?: string;
      timezone?: string;
    };
    send_welcome_email?: boolean;
    send_verification?: boolean;
  }) =>
    api.v1<StartOnboardingResponse>("/onboarding/start", {
      method: "POST",
      auth: false,
      body
    }),
  me: () => api.v1<OnboardingSession>("/onboarding/me"),
  autosave: (body: { step?: string; draft: Record<string, unknown> }) =>
    api.v1<OnboardingSession>("/onboarding/me/autosave", { method: "POST", body }),
  pause: () => api.v1<OnboardingSession>("/onboarding/me/pause", { method: "POST" }),
  resume: () => api.v1<OnboardingSession>("/onboarding/me/resume", { method: "POST" }),
  completeStep: (step: string, data: Record<string, unknown> = {}) =>
    api.v1<OnboardingStepAction>(`/onboarding/me/steps/${encodeURIComponent(step)}/complete`, {
      method: "POST",
      body: { data }
    }),
  skipStep: (step: string, reason?: string) =>
    api.v1<OnboardingStepAction>(`/onboarding/me/steps/${encodeURIComponent(step)}/skip`, {
      method: "POST",
      body: { reason: reason || null }
    }),
  uploadKnowledge: (file: File, knowledgeBaseId?: string) => {
    const form = new FormData();
    form.append("file", file);
    const qs = knowledgeBaseId
      ? `?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`
      : "";
    return api.v1<OnboardingStepAction>(`/onboarding/me/knowledge/upload${qs}`, {
      method: "POST",
      formData: form
    });
  },
  uploadKnowledgeWithProgress: (
    file: File,
    onProgress?: (percent: number) => void,
    knowledgeBaseId?: string
  ): Promise<OnboardingStepAction> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const qs = knowledgeBaseId
        ? `?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`
        : "";
      xhr.open("POST", `${apiPaths.v1}/onboarding/me/knowledge/upload${qs}`);
      const token =
        typeof window !== "undefined" ? window.localStorage.getItem("tht_access_token") : null;
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable || !onProgress) return;
        onProgress(Math.round((ev.loaded / ev.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(xhr.responseText ? JSON.parse(xhr.responseText) : ({} as OnboardingStepAction));
          } catch {
            reject(new Error("Invalid upload response"));
          }
          return;
        }
        let message = `Upload failed (${xhr.status})`;
        try {
          const body = JSON.parse(xhr.responseText);
          message = body?.error || body?.detail || body?.message || message;
          if (typeof body?.detail === "object" && body.detail?.error) message = body.detail.error;
        } catch {
          /* ignore */
        }
        reject(new Error(typeof message === "string" ? message : `Upload failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Upload network error"));
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    });
  }
};

/** Platform Super Admin — reuses /admin, /monitoring, companies, users, plans */
export type PlatformOverview = {
  active_users: number;
  companies: number;
  agents: number;
  published_agents: number;
  knowledge_bases: number;
  marketplace_installs: number;
  product_generations: number;
  billing_summary: {
    active_subscriptions?: number;
    revenue_paid?: number;
    amount_due_open?: number;
  };
  onboarding?: Record<string, unknown>;
  deployments?: Record<string, unknown>;
  generated_at: string;
};

export type SystemHealth = {
  status: string;
  api: Record<string, unknown>;
  database: Record<string, unknown>;
  redis: Record<string, unknown>;
  queue: Record<string, unknown>;
  storage: Record<string, unknown>;
  workers: Record<string, unknown>;
  ai_providers: Record<string, unknown>;
  email_queue?: Record<string, unknown>;
  background_jobs?: Record<string, unknown>;
};

export type ExecutiveDashboard = {
  generated_at: string;
  workspaces: number;
  active_companies?: number;
  active_users: number;
  new_signups: number;
  active_agents: number;
  knowledge_bases: number;
  widgets: number;
  ai_requests: number;
  ai_usage?: number;
  token_usage: number;
  api_usage: number;
  ai_cost: number;
  provider_cost?: number;
  global_revenue?: number;
  revenue: number;
  monthly_revenue?: number;
  failed_payments?: number;
  mrr: number;
  arr: number;
  active_subscriptions: number;
  churn: number;
  conversion_rate: number;
  signups_24h: number;
  signups_7d: number;
  signups_30d: number;
  revenue_series?: Array<{ period: string; revenue: number }>;
  ai_series?: Array<{ period: string; requests: number; tokens?: number }>;
};

export const platformAdminApi = {
  overview: () => api.v1<PlatformOverview>("/admin/overview"),
  executive: () => api.v1<ExecutiveDashboard>("/admin/executive"),
  aiAnalytics: (days = 30) => api.v1<Record<string, unknown>>(`/admin/ai-analytics?days=${days}`),
  workspaceOps: (companyId: string) =>
    api.v1<Record<string, unknown>>(`/admin/workspaces/${companyId}/ops`),
  logs: (category = "all", limit = 50) =>
    api.v1<{ category: string; total: number; items: Array<Record<string, unknown>> }>(
      `/admin/logs?category=${encodeURIComponent(category)}&limit=${limit}`
    ),
  marketplaceAnalytics: (days = 30) =>
    api.v1<Record<string, unknown>>(`/admin/marketplace-analytics?days=${days}`),
  inviteUser: (body: {
    email: string;
    company_id: string;
    role: string;
    first_name?: string;
    last_name?: string;
  }) =>
    api.v1<{ user: Record<string, unknown>; temporary_password: string; note: string }>(
      "/admin/users/invite",
      { method: "POST", body }
    ),
  resetPassword: (userId: string) =>
    api.v1<{ user_id: string; email: string; temporary_password: string }>(
      `/admin/users/${userId}/reset-password`,
      { method: "POST" }
    ),
  export: (kind: string, format: "csv" | "xlsx" | "pdf" = "csv") =>
    api.v1<{
      format: string;
      filename: string;
      content_type: string;
      encoding: string;
      content: string;
      row_count: number;
    }>("/admin/export", { method: "POST", body: { kind, format } }),
  jobs: (limit = 50) => api.v1<Record<string, unknown>>(`/operations/jobs?limit=${limit}`),
  observability: () => api.v1<Record<string, unknown>>("/monitoring/observability"),
  health: () => api.v1<SystemHealth>("/monitoring/health"),
  impersonateCompany: (company_id: string, reason?: string) =>
    api.v1<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
      company_id: string;
      company_name: string;
      company_slug: string;
      user_id: string;
      user_email: string;
      user_role: string;
      impersonated_by: string;
    }>("/admin/impersonate/company", {
      method: "POST",
      body: { company_id, reason: reason || null }
    })
};

/** Founder/CEO Command Center — read-only platform KPIs (Super Admin). */
export type CommandCenterDashboard = {
  revenue: number | null;
  mrr: number | null;
  customers: number | null;
  active_projects: number | null;
  leads: number | null;
  conversion: number | null;
  ai_tasks: number | null;
  human_escalations: number | null;
  ai_cost: number | null;
};

export type CeoAnalysis = {
  generated_at: string;
  metrics_snapshot: CommandCenterDashboard;
  business_status: string;
  problems: string[];
  opportunities: string[];
  you_must_decide: string[];
  recommendations: string[];
  provider?: string | null;
  model_used?: string | null;
};

export const commandCenterApi = {
  dashboard: () => api.v1<CommandCenterDashboard>("/command-center/dashboard"),
  ceoAnalysis: () =>
    api.v1<CeoAnalysis>("/command-center/ceo-analysis", { method: "POST" })
};

// Coding AI — thin proxy to the separate AI_Project AgentRuntime, mounted
// at /api/v1/coding-agent (app/coding_agent on the backend). Unlike
// studioApi/staticSitesApi above, this uses api.v1 (not api.apiV2) since
// it's a different router family. No list-tasks endpoint exists.
export const codingAgentApi = {
  createTask: (body: import("@/lib/coding-agent").CodingTaskCreateRequest, idempotencyKey: string) =>
    api.v1<import("@/lib/coding-agent").CodingTask>("/coding-agent/tasks", {
      method: "POST",
      body,
      headers: { "Idempotency-Key": idempotencyKey }
    }),
  getTask: (taskId: string) =>
    api.v1<import("@/lib/coding-agent").CodingTask>(`/coding-agent/tasks/${taskId}`),
  cancelTask: (taskId: string) =>
    api.v1<import("@/lib/coding-agent").CodingTaskCancelResult>(`/coding-agent/tasks/${taskId}/cancel`, {
      method: "POST"
    })
};

// THTWAAT Deploy — static HTML/ZIP sites. Sibling to studioApi, not a
// replacement — see app/static_sites on the backend.
export const staticSitesApi = {
  list: () =>
    api.apiV2<import("@/lib/static-sites").StaticSiteList>("/studio/static-sites"),
  create: (name: string) =>
    api.apiV2<import("@/lib/static-sites").StaticSite>("/studio/static-sites", {
      method: "POST",
      body: { name }
    }),
  get: (id: string) =>
    api.apiV2<import("@/lib/static-sites").StaticSite>(`/studio/static-sites/${id}`),
  listDeployments: (id: string) =>
    api.apiV2<import("@/lib/static-sites").StaticSiteDeploymentList>(
      `/studio/static-sites/${id}/deployments`
    ),
  getDeployment: (id: string, deploymentId: string) =>
    api.apiV2<import("@/lib/static-sites").StaticSiteDeployment>(
      `/studio/static-sites/${id}/deployments/${deploymentId}`
    ),
  deploymentStreamUrl: (id: string, deploymentId: string) =>
    `/api/v2/studio/static-sites/${id}/deployments/${deploymentId}/stream`,
  rollback: (id: string, body?: { deployment_id?: string }) =>
    api.apiV2<import("@/lib/static-sites").StaticSiteDeployment>(
      `/studio/static-sites/${id}/rollback`,
      { method: "POST", body: body || {} }
    ),
  /** XHR upload with progress — same recipe as knowledgeApi.uploadWithProgress. */
  uploadWithProgress: (
    siteId: string,
    file: File,
    opts: { domainMode?: "free_subdomain" | "custom"; domain?: string },
    onProgress?: (percent: number) => void
  ): Promise<import("@/lib/static-sites").StaticSiteDeployment> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${apiPaths.apiV2}/studio/static-sites/${siteId}/upload`;
      xhr.open("POST", url);
      const token = typeof window !== "undefined" ? window.localStorage.getItem("tht_access_token") : null;
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable || !onProgress) return;
        onProgress(Math.round((ev.loaded / ev.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(xhr.responseText ? JSON.parse(xhr.responseText) : {});
          } catch {
            reject(new Error("Unexpected response from server"));
          }
          return;
        }
        let message = `Deploy failed (${xhr.status})`;
        try {
          const body = JSON.parse(xhr.responseText);
          message = body?.detail || body?.error || body?.message || message;
          if (typeof body?.detail === "object" && body.detail?.error) message = body.detail.error;
        } catch {
          /* ignore */
        }
        reject(new Error(typeof message === "string" ? message : `Deploy failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Upload network error"));
      const form = new FormData();
      form.append("file", file);
      form.append("domain_mode", opts.domainMode || "free_subdomain");
      if (opts.domain) form.append("domain", opts.domain);
      xhr.send(form);
    });
  }
};

// THTWAAT Deploy — environment variables (Phase 4A/4B backend, Phase 4C UI).
// Site-scoped, same auth/company-isolation as staticSitesApi above — no
// separate fetch/auth logic. GET/list responses never carry a `value` field
// (see app/static_sites/schemas.py's StaticSiteEnvVarResponse) — only
// metadata ever comes back from these calls.
export const envVarsApi = {
  list: (siteId: string, environment?: string) =>
    api.apiV2<import("@/lib/env-vars").EnvVarList>(
      `/studio/static-sites/${siteId}/env-vars${environment ? `?environment=${encodeURIComponent(environment)}` : ""}`
    ),
  create: (siteId: string, body: import("@/lib/env-vars").EnvVarCreateRequest) =>
    api.apiV2<import("@/lib/env-vars").EnvVar>(`/studio/static-sites/${siteId}/env-vars`, {
      method: "POST",
      body
    }),
  update: (siteId: string, envId: string, body: import("@/lib/env-vars").EnvVarUpdateRequest) =>
    api.apiV2<import("@/lib/env-vars").EnvVar>(`/studio/static-sites/${siteId}/env-vars/${envId}`, {
      method: "PATCH",
      body
    }),
  remove: (siteId: string, envId: string) =>
    api.apiV2<void>(`/studio/static-sites/${siteId}/env-vars/${envId}`, { method: "DELETE" })
};

// THTWAAT Deploy Phase 5B — GitHub Connect. Site-scoped, same auth/company-
// isolation as staticSitesApi/envVarsApi above. The frontend never
// constructs a GitHub API URL or handles a token here — every call goes
// through the existing THTWAAT backend, which mints/discards GitHub
// installation tokens server-side (see app/static_sites/github_client.py).
export const githubApi = {
  // GET .../github 404s when nothing is connected yet (see
  // app/static_sites/github_service.py::_get_connection) — that is this
  // feature's normal "not connected" state, not an error, so it is mapped
  // to `null` here rather than left for every caller to catch separately.
  getConnection: async (siteId: string): Promise<import("@/lib/github").GitHubConnection | null> => {
    try {
      return await api.apiV2<import("@/lib/github").GitHubConnection>(`/studio/static-sites/${siteId}/github`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },
  // Returns a GitHub-hosted authorize_url only — the caller must navigate
  // the browser there (window.location.href), never fetch it.
  connect: (siteId: string) =>
    api.apiV2<import("@/lib/github").GitHubConnectStartResponse>(`/studio/static-sites/${siteId}/github/connect`),
  listRepositories: (siteId: string, page = 1, perPage = 30) =>
    api.apiV2<import("@/lib/github").GitHubRepositoryList>(
      `/studio/static-sites/${siteId}/github/repositories?page=${page}&per_page=${perPage}`
    ),
  listBranches: (siteId: string, owner: string, repo: string, page = 1, perPage = 30) =>
    api.apiV2<import("@/lib/github").GitHubBranchList>(
      `/studio/static-sites/${siteId}/github/branches?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&page=${page}&per_page=${perPage}`
    ),
  selectRepository: (siteId: string, body: import("@/lib/github").GitHubSelectRepositoryRequest) =>
    api.apiV2<import("@/lib/github").GitHubConnection>(`/studio/static-sites/${siteId}/github/select`, {
      method: "POST",
      body
    }),
  disconnect: (siteId: string) => api.apiV2<void>(`/studio/static-sites/${siteId}/github`, { method: "DELETE" })
};

// THTWAAT Deploy Phase 6A — Preview Deployments. Site-scoped, same auth/
// company-isolation as staticSitesApi/githubApi above. Previews are only
// ever CREATED/advanced/torn down by the GitHub webhook itself
// (app/static_sites/github_webhook_router.py) — every call here is
// read/manage only for an authenticated company owner/admin. Follows the
// page/per_page query-string convention githubApi.listRepositories/
// listBranches already use (not staticSitesApi.listDeployments's
// unpaginated shape), since preview history can grow large over a repo's
// lifetime.
export const previewDeploymentsApi = {
  list: (siteId: string, page = 1, perPage = 30) =>
    api.apiV2<import("@/lib/preview-deployments").PreviewDeploymentList>(
      `/studio/static-sites/${siteId}/previews?page=${page}&per_page=${perPage}`
    ),
  get: (siteId: string, previewId: string) =>
    api.apiV2<import("@/lib/preview-deployments").PreviewDeployment>(
      `/studio/static-sites/${siteId}/previews/${previewId}`
    ),
  streamUrl: (siteId: string, previewId: string) =>
    `/api/v2/studio/static-sites/${siteId}/previews/${previewId}/stream`,
  close: (siteId: string, previewId: string) =>
    api.apiV2<import("@/lib/preview-deployments").PreviewDeployment>(
      `/studio/static-sites/${siteId}/previews/${previewId}`,
      { method: "DELETE" }
    )
};
