import { api } from "@/lib/api";
import { apiPaths } from "@/lib/config";
import type {
  Agent,
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
  sendOtp: (body: { purpose: string; email: string }) =>
    api.v1("/auth/send-otp", { method: "POST", auth: false, body }),
  verifyOtp: (body: { purpose: string; email: string; code: string }) =>
    api.v1("/auth/verify-otp", { method: "POST", auth: false, body }),
  forgotPassword: (email: string) =>
    api.v1("/auth/forgot-password", { method: "POST", auth: false, body: { email } }),
  resetPassword: (body: { email: string; code: string; new_password: string }) =>
    api.v1("/auth/reset-password", { method: "POST", auth: false, body })
};

export const agentsApi = {
  list: () => api.v2<Agent[]>("/agents"),
  get: (id: string) => api.v2<Agent>(`/agents/${id}`),
  create: (body: Record<string, unknown>) => api.v2<Agent>("/agents", { method: "POST", body }),
  publish: (id: string) => api.v1<PublishResult>(`/agents/${id}/publish`, { method: "POST" }),
  unpublish: (id: string) => api.v1(`/agents/${id}/unpublish`, { method: "POST" }),
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
  plans: () => api.v1<Plan[]>("/payments/plans/"),
  plansAdmin: () => api.v1<Plan[]>("/payments/plans/?include_inactive=true"),
  updatePlan: (id: string, body: Record<string, unknown>) =>
    api.v1<Plan>(`/payments/plans/${id}`, { method: "PATCH", body }),
  subscription: () => api.v1<Subscription>("/payments/subscriptions/me"),
  invoices: () => api.v1<Invoice[]>("/payments/invoices"),
  providers: () =>
    api.v1<{
      stripe: { available: boolean; configured: boolean; flag_enabled: boolean };
      razorpay: { available: boolean; configured: boolean; flag_enabled: boolean };
      default: string;
    }>("/payments/subscriptions/providers"),
  razorpayOrder: (body: {
    plan_id: string;
    customer_name: string;
    customer_email: string;
    customer_phone?: string;
    coupon_code?: string;
    interval?: string;
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
  sendMessage: (id: string, content: string) =>
    api.v2<{ user_message: unknown; assistant_message: unknown }>(
      `/conversations/${id}/messages`,
      { method: "POST", body: { content } }
    )
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
      slug: string;
      display_name?: string;
      industry?: string;
      timezone?: string;
    };
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
  active_users: number;
  new_signups: number;
  active_agents: number;
  knowledge_bases: number;
  widgets: number;
  ai_requests: number;
  token_usage: number;
  api_usage: number;
  ai_cost: number;
  revenue: number;
  mrr: number;
  arr: number;
  active_subscriptions: number;
  churn: number;
  conversion_rate: number;
  signups_24h: number;
  signups_7d: number;
  signups_30d: number;
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
