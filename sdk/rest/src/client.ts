import { HttpCore } from "./core/http";
import type { RestClientConfig } from "./core/types";
import { AuthResource } from "./resources/auth";
import { CompaniesResource } from "./resources/companies";
import { UsersResource } from "./resources/users";
import { AgentsResource } from "./resources/agents";
import { KnowledgeResource } from "./resources/knowledge";
import { ConversationsResource } from "./resources/conversations";
import { PaymentsResource, BillingResource } from "./resources/payments";
import { AnalyticsResource } from "./resources/analytics";
import { DomainsResource } from "./resources/domains";
import { WidgetResource } from "./resources/widget";

export const REST_SDK_VERSION = "1.0.0";

/**
 * Official OpenAPI-backed REST client for THTWAAT.
 *
 * Types for request/response bodies come from `src/generated/schema.ts`
 * (generated via `npm run generate` from openapi.json).
 */
export class RestClient {
  readonly version = REST_SDK_VERSION;
  readonly http: HttpCore;

  readonly auth: AuthResource;
  readonly companies: CompaniesResource;
  readonly users: UsersResource;
  readonly agents: AgentsResource;
  readonly knowledge: KnowledgeResource;
  readonly conversations: ConversationsResource;
  readonly payments: PaymentsResource;
  readonly billing: BillingResource;
  readonly analytics: AnalyticsResource;
  readonly domains: DomainsResource;
  readonly widget: WidgetResource;

  readonly get: HttpCore["get"];
  readonly post: HttpCore["post"];
  readonly put: HttpCore["put"];
  readonly patch: HttpCore["patch"];
  readonly delete: HttpCore["delete"];
  readonly upload: HttpCore["upload"];
  readonly streamSSE: HttpCore["streamSSE"];

  constructor(config: RestClientConfig = {}) {
    this.http = new HttpCore(config);
    this.auth = new AuthResource(this.http);
    this.companies = new CompaniesResource(this.http);
    this.users = new UsersResource(this.http);
    this.agents = new AgentsResource(this.http);
    this.knowledge = new KnowledgeResource(this.http);
    this.conversations = new ConversationsResource(this.http);
    this.payments = new PaymentsResource(this.http);
    this.billing = new BillingResource(this.http);
    this.analytics = new AnalyticsResource(this.http);
    this.domains = new DomainsResource(this.http);
    this.widget = new WidgetResource(this.http);

    this.get = this.http.get.bind(this.http);
    this.post = this.http.post.bind(this.http);
    this.put = this.http.put.bind(this.http);
    this.patch = this.http.patch.bind(this.http);
    this.delete = this.http.delete.bind(this.http);
    this.upload = this.http.upload.bind(this.http);
    this.streamSSE = this.http.streamSSE.bind(this.http);
  }

  setApiKey(key: string): this {
    this.http.setApiKey(key);
    return this;
  }

  setBearerToken(token: string): this {
    this.http.setBearerToken(token);
    return this;
  }

  setSessionToken(token: string): this {
    this.http.setSessionToken(token);
    return this;
  }
}

export default RestClient;
