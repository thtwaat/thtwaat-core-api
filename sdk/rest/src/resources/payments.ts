import type { HttpCore } from "../core/http";
import { normalizePage } from "../core/pagination";
import type { PageParams } from "../core/types";

export class PaymentsResource {
  constructor(private readonly http: HttpCore) {}

  async list(params: PageParams = {}) {
    const raw = await this.http.get("/api/v1/payments/", {
      query: params as Record<string, string | number | boolean>,
    });
    return normalizePage(raw, params);
  }

  create(body: unknown) {
    return this.http.post("/api/v1/payments/", body);
  }

  get(paymentId: string) {
    return this.http.get(`/api/v1/payments/${paymentId}`);
  }

  status(paymentId: string) {
    return this.http.get(`/api/v1/payments/${paymentId}/status`);
  }

  refund(paymentId: string, body?: unknown) {
    return this.http.post(`/api/v1/payments/${paymentId}/refund`, body);
  }
}

export class BillingResource {
  constructor(private readonly http: HttpCore) {}

  listPlans() {
    return this.http.get("/api/v1/payments/plans/");
  }

  getPlan(planId: string) {
    return this.http.get(`/api/v1/payments/plans/${planId}`);
  }

  me() {
    return this.http.get("/api/v1/payments/subscriptions/me");
  }

  history() {
    return this.http.get("/api/v1/payments/subscriptions/history");
  }

  cancel(body?: unknown) {
    return this.http.post("/api/v1/payments/subscriptions/cancel", body);
  }

  razorpayOrder(body: unknown) {
    return this.http.post("/api/v1/payments/subscriptions/razorpay/order", body);
  }

  razorpayVerify(body: unknown) {
    return this.http.post("/api/v1/payments/subscriptions/razorpay/verify", body);
  }

  stripeCheckout(body: unknown) {
    return this.http.post("/api/v1/payments/subscriptions/stripe/checkout", body);
  }

  listInvoices(params: PageParams = {}) {
    return this.http.get("/api/v1/payments/invoices/", {
      query: params as Record<string, string | number | boolean>,
    });
  }

  getInvoice(invoiceId: string) {
    return this.http.get(`/api/v1/payments/invoices/${invoiceId}`);
  }
}
