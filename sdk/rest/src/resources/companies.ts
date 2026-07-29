import type { HttpCore } from "../core/http";
import { iteratePages, normalizePage } from "../core/pagination";
import type { PageParams } from "../core/types";
import type { components } from "../generated/schema";

type Schemas = components["schemas"];

export class CompaniesResource {
  constructor(private readonly http: HttpCore) {}

  async list(params: PageParams & { status?: string; plan?: string } = {}) {
    const raw = await this.http.get("/api/v1/companies/", {
      query: params as Record<string, string | number | boolean>,
    });
    return normalizePage<Schemas["CompanyResponse"]>(raw, params);
  }

  iterate(params: PageParams = {}) {
    return iteratePages((p) => this.list({ ...params, ...p }), params);
  }

  create(body: Schemas["CompanyCreate"]) {
    return this.http.post<Schemas["CompanyResponse"]>("/api/v1/companies/", body);
  }

  get(companyId: string) {
    return this.http.get<Schemas["CompanyResponse"]>(`/api/v1/companies/${companyId}`);
  }

  getBySlug(slug: string) {
    return this.http.get<Schemas["CompanyResponse"]>(`/api/v1/companies/slug/${slug}`);
  }

  update(companyId: string, body: Schemas["CompanyUpdate"]) {
    return this.http.patch<Schemas["CompanyResponse"]>(`/api/v1/companies/${companyId}`, body);
  }
}
