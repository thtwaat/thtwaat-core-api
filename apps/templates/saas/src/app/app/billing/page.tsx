"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { billingApi, usageApi } from "@/lib/services";
import { site } from "@/lib/config";
import { useAuth } from "@/lib/auth";
import { formatDate, formatNumber } from "@/lib/utils";
import {
  countryCurrency,
  countryFromBrowserLocale,
  readStoredBillingCountry,
  resolveInitialBillingCountry,
  writeStoredBillingCountry
} from "@/lib/billing-countries";
import {
  formatPlanPrice,
  pickBillingCheckoutProvider,
  resolvePlanDisplayAmount,
  resolveRazorpayCheckoutKey
} from "@/lib/billing-providers";
import {
  loadRazorpayCheckoutScript,
  openRazorpayCheckout,
  runRazorpayCheckout
} from "@/lib/razorpay-checkout";
import { BillingCountrySelector } from "@/components/billing/BillingCountrySelector";
import { PageHeader, EmptyState, Progress, Stat } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function BillingPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [coupon, setCoupon] = useState("");
  const [country, setCountry] = useState<string | null>(() => readStoredBillingCountry());
  const [countryReady, setCountryReady] = useState(() => Boolean(readStoredBillingCountry()));

  // Bootstrap country when no local preference: server → browser locale → US
  const bootstrapCtx = useQuery({
    queryKey: ["billing-context-bootstrap"],
    queryFn: () => billingApi.billingContext(),
    enabled: !countryReady
  });

  useEffect(() => {
    if (countryReady) return;
    if (bootstrapCtx.isLoading) return;
    if (bootstrapCtx.isError) {
      const fallback =
        resolveInitialBillingCountry({
          stored: readStoredBillingCountry(),
          browserCountry: countryFromBrowserLocale()
        }) || "US";
      setCountry(fallback);
      writeStoredBillingCountry(fallback);
      setCountryReady(true);
      return;
    }
    if (!bootstrapCtx.data) return;
    const resolved = resolveInitialBillingCountry({
      stored: readStoredBillingCountry(),
      serverCountry: bootstrapCtx.data.country || bootstrapCtx.data.country_code,
      serverSource: bootstrapCtx.data.source,
      browserCountry: countryFromBrowserLocale()
    });
    setCountry(resolved);
    writeStoredBillingCountry(resolved);
    setCountryReady(true);
  }, [countryReady, bootstrapCtx.isLoading, bootstrapCtx.isError, bootstrapCtx.data]);

  const billingCountry = country || "US";

  const plans = useQuery({
    queryKey: ["plans", billingCountry],
    queryFn: () => billingApi.plans(billingCountry),
    enabled: countryReady
  });
  const sub = useQuery({ queryKey: ["subscription"], queryFn: billingApi.subscription });
  const invoices = useQuery({ queryKey: ["invoices"], queryFn: billingApi.invoices });
  const usage = useQuery({ queryKey: ["usage-current"], queryFn: usageApi.current });
  const providers = useQuery({
    queryKey: ["billing-providers", billingCountry],
    queryFn: () => billingApi.providers(billingCountry),
    enabled: countryReady
  });
  const billingCtx = useQuery({
    queryKey: ["billing-context", billingCountry],
    queryFn: () => billingApi.billingContext(billingCountry),
    enabled: countryReady
  });

  const displayCurrency = (
    billingCtx.data?.currency ||
    providers.data?.region?.currency ||
    countryCurrency(billingCountry)
  ).toUpperCase();

  const razorpayKey = useMemo(
    () => resolveRazorpayCheckoutKey(providers.data, site.razorpayKey),
    [providers.data]
  );
  const checkoutProvider = useMemo(
    () => pickBillingCheckoutProvider(providers.data, site.razorpayKey, billingCtx.data),
    [providers.data, billingCtx.data]
  );

  async function refreshBillingState() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["subscription"] }),
      qc.invalidateQueries({ queryKey: ["invoices"] }),
      qc.invalidateQueries({ queryKey: ["usage-current"] }),
      qc.invalidateQueries({ queryKey: ["plans", billingCountry] }),
      qc.invalidateQueries({ queryKey: ["billing-providers", billingCountry] }),
      qc.invalidateQueries({ queryKey: ["billing-context", billingCountry] })
    ]);
  }

  async function handleCountryChange(next: string) {
    const code = next.toUpperCase();
    if (code === billingCountry) return;
    setCountry(code);
    writeStoredBillingCountry(code);
    try {
      await billingApi.setBillingCountry(code);
    } catch {
      // Local selection still applies; workspace persist is best-effort.
    }
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["plans"] }),
      qc.invalidateQueries({ queryKey: ["billing-providers"] }),
      qc.invalidateQueries({ queryKey: ["billing-context"] })
    ]);
  }

  const remainingHint = useMemo(() => {
    const progress = usage.data?.progress || [];
    if (!progress.length) return "—";
    const first = progress[0];
    const left = Math.max(0, Number(first.limit || 0) - Number(first.current || 0));
    return `${formatNumber(left)} ${first.dimension.replaceAll("_", " ")} left`;
  }, [usage.data]);

  const upgrade = useMutation({
    mutationFn: async (plan: {
      id: string;
      name: string;
      amount?: number;
      price?: number;
      is_custom_pricing?: boolean;
    }) => {
      if (plan.is_custom_pricing) {
        throw new Error("Enterprise uses custom pricing. Contact sales.");
      }
      const price = Number(plan.amount ?? plan.price ?? 0);
      if (!(price > 0)) {
        return billingApi.changePlan({
          plan_id: plan.id,
          coupon_code: coupon || undefined,
          country: billingCountry
        });
      }

      const providerStatus = (await billingApi.providers(billingCountry)) || providers.data;
      const context = (await billingApi.billingContext(billingCountry)) || billingCtx.data;
      const chosen = pickBillingCheckoutProvider(providerStatus, site.razorpayKey, context);
      const key = resolveRazorpayCheckoutKey(providerStatus, site.razorpayKey);

      if (chosen === "razorpay" && key) {
        const customerName =
          [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() ||
          user?.email?.split("@")[0] ||
          "Customer";
        const customerEmail = user?.email || "";

        return runRazorpayCheckout({
          planId: plan.id,
          planName: plan.name,
          customerName,
          customerEmail,
          deps: {
            razorpayKey: key,
            createOrder: (body) =>
              billingApi.razorpayOrder({
                ...body,
                coupon_code: coupon || undefined,
                country: billingCountry
              }),
            verifyPayment: billingApi.razorpayVerify,
            loadCheckoutScript: loadRazorpayCheckoutScript,
            openCheckout: openRazorpayCheckout
          }
        });
      }

      if (chosen === "stripe") {
        const success_url = `${window.location.origin}/app/billing?upgraded=1`;
        const cancel_url = `${window.location.origin}/app/billing?cancelled=1`;
        const session = await billingApi.stripeCheckout({
          plan_id: plan.id,
          success_url,
          cancel_url,
          coupon_code: coupon || undefined,
          country: billingCountry
        });
        if (session.checkout_url) {
          window.location.href = session.checkout_url;
          return { status: "redirect" as const };
        }
      }

      throw new Error(
        "No payment provider available. Enable Stripe or Razorpay (BILLING_ENABLE_* + secrets), and ensure Razorpay key_id is returned by /payments/subscriptions/providers."
      );
    },
    onSuccess: async (result) => {
      if (result && "provider" in result && result.provider === "manual") {
        toast.success("Plan updated");
        await refreshBillingState();
        return;
      }
      if (result && "status" in result && result.status === "redirect") return;
      if (!result || !("status" in result)) return;

      switch (result.status) {
        case "success":
          toast.success("Payment verified. Your plan is updating.");
          await refreshBillingState();
          break;
        case "cancelled":
          toast.message("Checkout cancelled");
          break;
        case "verify_failed":
          toast.error(result.error.message || "Payment verification failed");
          break;
        case "network_failed":
          toast.error(result.error.message || "Checkout failed. Please try again.");
          break;
        case "blocked":
          toast.message("Checkout already in progress");
          break;
      }
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const cancel = useMutation({
    mutationFn: () => billingApi.cancel(),
    onSuccess: () => {
      toast.success("Cancellation requested");
      qc.invalidateQueries({ queryKey: ["subscription"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const resume = useMutation({
    mutationFn: () => billingApi.resume(),
    onSuccess: () => {
      toast.success("Subscription resumed");
      qc.invalidateQueries({ queryKey: ["subscription"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const validateCoupon = useMutation({
    mutationFn: () => billingApi.validateCoupon(coupon),
    onSuccess: (res) => {
      if (res.valid) toast.success(`Coupon applied (${res.percent_off ?? res.amount_off} off)`);
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const planName =
    typeof sub.data?.plan === "string" ? sub.data.plan : sub.data?.plan?.name || usage.data?.plan || "free";

  return (
    <div className="space-y-6">
      <PageHeader title="Billing" description="Current plan, upgrades, invoices, usage, and quotas." />

      <BillingCountrySelector
        value={billingCountry}
        onChange={handleCountryChange}
        disabled={!countryReady}
      />
      <p className="text-xs text-muted">Prices shown in {displayCurrency}</p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Current plan" value={String(planName)} hint={sub.data?.status || "active"} />
        <Stat label="Messages used" value={formatNumber(usage.data?.usage?.ai_messages)} />
        <Stat label="Tokens used" value={formatNumber(usage.data?.usage?.total_tokens)} />
        <Stat label="Remaining quota" value={remainingHint} />
      </div>

      <Card>
        <CardHeader
          title="Subscription"
          action={
            <div className="flex flex-wrap gap-2">
              {sub.data?.cancel_at_period_end ? (
                <Button variant="secondary" size="sm" onClick={() => resume.mutate()} disabled={resume.isPending}>
                  Resume
                </Button>
              ) : sub.data?.status && !["canceled", "cancelled"].includes(String(sub.data.status)) ? (
                <Button variant="secondary" size="sm" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
                  Cancel
                </Button>
              ) : null}
            </div>
          }
        />
        <p className="text-sm text-muted">
          Status: <Badge>{sub.data?.status || "none"}</Badge>
          {sub.data?.cancel_at_period_end ? " · cancels at period end" : ""}
          {sub.data?.current_period_end ? ` · renews ${formatDate(sub.data.current_period_end)}` : ""}
        </p>
        <p className="mt-2 text-xs text-muted">
          Country: {billingCtx.data?.country || billingCountry} · Gateway{" "}
          {billingCtx.data?.gateway || checkoutProvider || "—"} · Currency {displayCurrency} ·
          Providers: Stripe {providers.data?.stripe?.available ? "on" : "off"} · Razorpay{" "}
          {checkoutProvider === "razorpay" || providers.data?.razorpay?.available ? "on" : "off"}
          {razorpayKey ? ` · key ${razorpayKey.slice(0, 10)}…` : ""}
        </p>
        <div className="mt-4 space-y-3">
          {(usage.data?.progress || []).slice(0, 8).map((p) => (
            <div key={p.dimension}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="capitalize">{p.dimension.replaceAll("_", " ")}</span>
                <span className="text-muted">
                  {formatNumber(p.current)} / {formatNumber(p.limit)}
                </span>
              </div>
              <Progress value={p.percent} />
            </div>
          ))}
        </div>
      </Card>

      <Card className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex-1 space-y-1.5 text-sm">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">Coupon</span>
          <Input
            placeholder="SAVE20"
            value={coupon}
            onChange={(e) => setCoupon(e.target.value.toUpperCase())}
          />
        </label>
        <Button
          variant="secondary"
          disabled={!coupon.trim() || validateCoupon.isPending}
          onClick={() => validateCoupon.mutate()}
        >
          Validate coupon
        </Button>
      </Card>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Upgrade / change plan</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {(plans.data || []).map((plan) => {
            const currency = (plan.display_currency || displayCurrency).toUpperCase();
            const price = resolvePlanDisplayAmount(plan, currency);
            const custom = Boolean(plan.is_custom_pricing);
            const yearly =
              currency === "INR"
                ? plan.yearly_price_inr
                : plan.yearly_price_usd ?? plan.yearly_amount;
            return (
              <Card key={plan.id}>
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <p className="mt-1 text-sm text-muted">{plan.description || plan.interval || "monthly"}</p>
                <p className="my-4 text-3xl font-semibold">
                  {custom ? "Custom" : formatPlanPrice(price, currency)}
                  {!custom ? (
                    <span className="text-sm font-normal text-muted">/{plan.interval || "month"}</span>
                  ) : null}
                </p>
                {yearly != null && !custom ? (
                  <p className="mb-3 text-xs text-muted">
                    Yearly {formatPlanPrice(yearly, currency)}
                  </p>
                ) : null}
                <Button
                  className="w-full"
                  onClick={() =>
                    upgrade.mutate({
                      id: plan.id,
                      name: plan.name,
                      amount: price ?? 0,
                      price: price ?? 0,
                      is_custom_pricing: custom
                    })
                  }
                  disabled={upgrade.isPending || custom || ((price ?? 0) > 0 && providers.isLoading)}
                >
                  {custom
                    ? "Contact sales"
                    : upgrade.isPending
                      ? "Processing…"
                      : `Choose ${plan.name}`}
                </Button>
              </Card>
            );
          })}
          {!plans.data?.length && countryReady && (
            <EmptyState title="No plans returned" description="No active plans are available yet." />
          )}
        </div>
      </div>

      <Card>
        <CardHeader title="Invoices & payment history" />
        <div className="space-y-2">
          {(invoices.data || []).map((invoice) => (
            <div
              key={invoice.id}
              className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm"
            >
              <div>
                <p className="font-medium">{invoice.number || invoice.id.slice(0, 8)}</p>
                <p className="text-xs text-muted">{formatDate(invoice.created_at)}</p>
              </div>
              <div className="flex items-center gap-3">
                <span>
                  {invoice.currency || "USD"} {invoice.total ?? invoice.amount ?? invoice.amount_paid ?? 0}
                </span>
                <Badge tone={invoice.status === "paid" ? "success" : "warn"}>{invoice.status}</Badge>
                {invoice.invoice_pdf || invoice.hosted_url ? (
                  <a
                    className="text-xs font-medium text-teal-700 hover:underline"
                    href={invoice.invoice_pdf || invoice.hosted_url || "#"}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download
                  </a>
                ) : null}
              </div>
            </div>
          ))}
          {!invoices.data?.length && <EmptyState title="No invoices yet" />}
        </div>
      </Card>
    </div>
  );
}
