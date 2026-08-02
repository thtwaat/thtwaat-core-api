"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { billingApi, usageApi } from "@/lib/services";
import { site } from "@/lib/config";
import { useAuth } from "@/lib/auth";
import { formatDate, formatNumber } from "@/lib/utils";
import {
  loadRazorpayCheckoutScript,
  openRazorpayCheckout,
  runRazorpayCheckout
} from "@/lib/razorpay-checkout";
import { PageHeader, EmptyState, Progress, Stat } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function BillingPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const plans = useQuery({ queryKey: ["plans"], queryFn: billingApi.plans });
  const sub = useQuery({ queryKey: ["subscription"], queryFn: billingApi.subscription });
  const invoices = useQuery({ queryKey: ["invoices"], queryFn: billingApi.invoices });
  const usage = useQuery({ queryKey: ["usage-current"], queryFn: usageApi.current });

  async function refreshBillingState() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["subscription"] }),
      qc.invalidateQueries({ queryKey: ["invoices"] }),
      qc.invalidateQueries({ queryKey: ["usage-current"] }),
      qc.invalidateQueries({ queryKey: ["plans"] })
    ]);
  }

  const upgrade = useMutation({
    mutationFn: async (plan: { id: string; name: string }) => {
      if (site.razorpayKey) {
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
            razorpayKey: site.razorpayKey,
            createOrder: billingApi.razorpayOrder,
            verifyPayment: billingApi.razorpayVerify,
            loadCheckoutScript: loadRazorpayCheckoutScript,
            openCheckout: openRazorpayCheckout
          }
        });
      }

      const data = await billingApi.stripeCheckout(
        plan.id,
        `${site.url}/app/billing?success=1`,
        `${site.url}/app/billing`
      );
      return { status: "stripe" as const, data };
    },
    onSuccess: async (result) => {
      if (result && "status" in result && result.status === "stripe") {
        const url = result.data.checkout_url;
        if (url) window.location.href = url;
        return;
      }

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

  const planName =
    typeof sub.data?.plan === "string" ? sub.data.plan : sub.data?.plan?.name || usage.data?.plan || "free";

  return (
    <div className="space-y-6">
      <PageHeader title="Billing" description="Current plan, upgrades, invoices, usage, and quotas." />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Current plan" value={String(planName)} hint={sub.data?.status || "active"} />
        <Stat label="Messages used" value={formatNumber(usage.data?.usage?.ai_messages)} />
        <Stat label="Quota items" value={String(usage.data?.progress?.length || 0)} />
      </div>

      <Card>
        <CardHeader
          title="Subscription"
          action={
            sub.data?.status && sub.data.status !== "canceled" ? (
              <Button variant="secondary" size="sm" onClick={() => cancel.mutate()}>
                Cancel
              </Button>
            ) : undefined
          }
        />
        <p className="text-sm text-muted">
          Status: <Badge>{sub.data?.status || "none"}</Badge>
          {sub.data?.current_period_end ? ` · renews ${formatDate(sub.data.current_period_end)}` : ""}
        </p>
        <div className="mt-4 space-y-3">
          {(usage.data?.progress || []).slice(0, 5).map((p) => (
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

      <div>
        <h2 className="mb-3 text-lg font-semibold">Upgrade</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {(plans.data || []).map((plan) => {
            const price = plan.amount ?? plan.price ?? 0;
            return (
              <Card key={plan.id}>
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <p className="mt-1 text-sm text-muted">{plan.description || plan.interval || "monthly"}</p>
                <p className="my-4 text-3xl font-semibold">
                  ${price}
                  <span className="text-sm font-normal text-muted">/{plan.interval || "mo"}</span>
                </p>
                <Button
                  className="w-full"
                  onClick={() => upgrade.mutate({ id: plan.id, name: plan.name })}
                  disabled={upgrade.isPending}
                >
                  {upgrade.isPending ? "Processing…" : `Choose ${plan.name}`}
                </Button>
              </Card>
            );
          })}
          {!plans.data?.length && <EmptyState title="No plans returned" description="No active plans are available yet." />}
        </div>
      </div>

      <Card>
        <CardHeader title="Invoices" />
        <div className="space-y-2">
          {(invoices.data || []).map((invoice) => (
            <div key={invoice.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm">
              <div>
                <p className="font-medium">{invoice.number || invoice.id.slice(0, 8)}</p>
                <p className="text-xs text-muted">{formatDate(invoice.created_at)}</p>
              </div>
              <div className="flex items-center gap-3">
                <span>
                  {invoice.currency || "USD"} {invoice.total ?? invoice.amount ?? 0}
                </span>
                <Badge tone={invoice.status === "paid" ? "success" : "warn"}>{invoice.status}</Badge>
              </div>
            </div>
          ))}
          {!invoices.data?.length && <EmptyState title="No invoices yet" />}
        </div>
      </Card>
    </div>
  );
}
