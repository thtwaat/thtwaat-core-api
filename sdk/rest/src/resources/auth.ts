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

  sendOtp(body: unknown) {
    return this.http.post("/api/v1/auth/send-otp", body);
  }

  verifyOtp(body: unknown) {
    return this.http.post("/api/v1/auth/verify-otp", body);
  }

  forgotPassword(body: unknown) {
    return this.http.post("/api/v1/auth/forgot-password", body);
  }

  resetPassword(body: unknown) {
    return this.http.post("/api/v1/auth/reset-password", body);
  }
}
