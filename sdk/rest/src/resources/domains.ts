import type { HttpCore } from "../core/http";

/**
 * Domain Manager resource.
 */
export class DomainsResource {
  constructor(private readonly http: HttpCore) {}

  list() {
    return this.http.get("/api/v1/domains/");
  }

  dashboard() {
    return this.http.get("/api/v1/domains/dashboard");
  }

  create(body: {
    hostname: string;
    verification_method?: "TXT" | "CNAME";
    agent_id?: string;
    widget_id?: string;
    is_primary?: boolean;
  }) {
    return this.http.post("/api/v1/domains/", body);
  }

  get(domainId: string) {
    return this.http.get(`/api/v1/domains/${domainId}`);
  }

  update(
    domainId: string,
    body: {
      agent_id?: string | null;
      widget_id?: string | null;
      is_primary?: boolean;
      verification_method?: "TXT" | "CNAME";
    }
  ) {
    return this.http.patch(`/api/v1/domains/${domainId}`, body);
  }

  dns(domainId: string) {
    return this.http.get(`/api/v1/domains/${domainId}/dns`);
  }

  verify(domainId: string) {
    return this.http.post(`/api/v1/domains/${domainId}/verify`);
  }

  retry(domainId: string) {
    return this.http.post(`/api/v1/domains/${domainId}/retry`);
  }

  requestSsl(domainId: string) {
    return this.http.post(`/api/v1/domains/${domainId}/ssl/request`);
  }

  markSslIssued(domainId: string) {
    return this.http.post(`/api/v1/domains/${domainId}/ssl/issued`);
  }

  delete(domainId: string) {
    return this.http.delete(`/api/v1/domains/${domainId}`);
  }
}
