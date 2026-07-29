import type { HttpCore } from "../core/http";
import { normalizePage } from "../core/pagination";
import type { PageParams } from "../core/types";
import type { components } from "../generated/schema";

type Schemas = components["schemas"];

export class UsersResource {
  constructor(private readonly http: HttpCore) {}

  async list(params: PageParams = {}) {
    const raw = await this.http.get("/api/v1/users/", {
      query: params as Record<string, string | number | boolean>,
    });
    return normalizePage<Schemas["UserResponse"]>(raw, params);
  }

  create(body: Schemas["UserCreate"]) {
    return this.http.post<Schemas["UserResponse"]>("/api/v1/users/", body);
  }

  get(userId: string) {
    return this.http.get<Schemas["UserResponse"]>(`/api/v1/users/${userId}`);
  }

  update(userId: string, body: Schemas["UserUpdate"]) {
    return this.http.patch<Schemas["UserResponse"]>(`/api/v1/users/${userId}`, body);
  }

  delete(userId: string) {
    return this.http.delete(`/api/v1/users/${userId}`);
  }
}
