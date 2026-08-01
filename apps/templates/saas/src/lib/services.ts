import { api } from "@/lib/api";
import type {
  Agent,
  Company,
  Conversation,
  Domain,
  Invoice,
  KnowledgeBase,
  KnowledgeDocument,
  Plan,
  PublishResult,
  Subscription,
  UsageCurrent
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
  widget: (id: string) => api.v1<Record<string, unknown>>(`/agents/${id}/widget`)
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
  deleteDocument: (_baseId: string, docId: string) =>
    api.v2(`/knowledge/documents/${docId}`, { method: "DELETE" }),
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
  sslRequest: (id: string) => api.v1(`/domains/${id}/ssl/request`, { method: "POST" }),
  sslStatus: (id: string) => api.v1(`/domains/${id}/ssl/status`),
  remove: (id: string) => api.v1(`/domains/${id}`, { method: "DELETE" })
};

export const usageApi = {
  current: () => api.v1<UsageCurrent>("/usage/current"),
  dashboard: () => api.v1<Record<string, unknown>>("/usage/dashboard"),
  history: (days = 30) => api.v1<{ points: Array<{ day: string; dimension: string; quantity: number }> }>(`/usage/history?days=${days}`)
};

export const billingApi = {
  plans: () => api.v1<Plan[]>("/payments/plans", { auth: false }),
  subscription: () => api.v1<Subscription>("/payments/subscriptions/me"),
  invoices: () => api.v1<Invoice[]>("/payments/invoices"),
  razorpayOrder: (plan_id: string) =>
    api.v1<{ order_id: string }>("/payments/subscriptions/razorpay/order", {
      method: "POST",
      body: { plan_id }
    }),
  stripeCheckout: (plan_id: string, success_url: string, cancel_url: string) =>
    api.v1<{ checkout_url: string }>("/payments/subscriptions/stripe/checkout", {
      method: "POST",
      body: { plan_id, success_url, cancel_url }
    }),
  cancel: () => api.v1("/payments/subscriptions/cancel", { method: "POST" })
};

export const conversationsApi = {
  list: () => api.v2<Conversation[]>("/conversations")
};

export const companiesApi = {
  get: (id: string) => api.v1<Company>(`/companies/${id}`),
  update: (id: string, body: Record<string, unknown>) =>
    api.v1<Company>(`/companies/${id}`, { method: "PATCH", body }),
  create: (body: Record<string, unknown>) =>
    api.v1<Company>("/companies", { method: "POST", auth: false, body })
};

export const usersApi = {
  create: (body: Record<string, unknown>) =>
    api.v1("/users", { method: "POST", auth: false, body }),
  list: () => api.v1<Array<Record<string, unknown>>>("/users"),
  update: (id: string, body: Record<string, unknown>) => api.v1(`/users/${id}`, { method: "PATCH", body })
};

export const apiKeysApi = {
  list: () => api.v1<Array<Record<string, unknown>>>("/api-keys"),
  create: (body: { name?: string }) => api.v1("/api-keys", { method: "POST", body }),
  remove: (id: string) => api.v1(`/api-keys/${id}`, { method: "DELETE" })
};

export type TemplateCategory = {
  slug: string;
  name: string;
  count: number;
};

export type TemplateItem = {
  id: string;
  slug: string;
  name: string;
  category: string;
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
  created_at: string;
  installed: boolean;
  update_available: boolean;
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

export type MarketplaceDashboard = {
  featured: TemplateItem[];
  newest: TemplateItem[];
  installed_count: number;
  updates_count: number;
  categories: TemplateCategory[];
};

export const marketplaceApi = {  dashboard: () => api.v1<MarketplaceDashboard>("/marketplace/dashboard"),
  categories: () => api.v1<TemplateCategory[]>("/marketplace/categories"),
  list: (params?: { q?: string; category?: string; featured?: boolean; newest?: boolean; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.category) qs.set("category", params.category);
    if (params?.featured != null) qs.set("featured", String(params.featured));
    if (params?.newest) qs.set("newest", "true");
    if (params?.limit) qs.set("limit", String(params.limit));
    return api.v1<TemplateItem[]>(`/marketplace/templates${qs.size ? `?${qs}` : ""}`);
  },
  get: (idOrSlug: string) => api.v1<TemplateItem>(`/marketplace/templates/${idOrSlug}`),
  versions: (id: string) => api.v1<Array<Record<string, unknown>>>(`/marketplace/templates/${id}/versions`),
  installed: () => api.v1<Installation[]>("/marketplace/installed"),
  updates: () => api.v1<UpdateNotification[]>("/marketplace/updates"),
  install: (idOrSlug: string, body?: { create_api_key?: boolean; config_overrides?: Record<string, unknown> }) =>
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
    api.v1(`/marketplace/installations/${installId}`, { method: "DELETE" })
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
