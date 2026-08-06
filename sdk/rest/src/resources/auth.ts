import type { HttpCore } from "../core/http";
import type { components } from "../generated/schema";

type Schemas = components["schemas"];

export class AuthResource {
  constructor(private readonly http: HttpCore) {}

  login(body: Schemas["LoginRequest"]) {
    return this.http.post<Schemas["TokenResponse"]>("/api/v1/auth/login", body);
  }

  refresh(body: Schemas["RefreshRequest"]) {
    return this.http.post("/api/v1/auth/refresh", body);
  }

  logout() {
    return this.http.post("/api/v1/auth/logout");
  }

  me() {
    return this.http.get<Schemas["UserProfileResponse"]>("/api/v1/auth/me");
  }

  forgotPassword(body: { email: string }) {
    return this.http.post("/api/v1/auth/forgot-password", body);
  }

  resetPassword(body: { token: string; new_password: string }) {
    return this.http.post("/api/v1/auth/reset-password", body);
  }

  google(body: { id_token: string }) {
    return this.http.post<Schemas["TokenResponse"]>("/api/v1/auth/google", body);
  }
}
