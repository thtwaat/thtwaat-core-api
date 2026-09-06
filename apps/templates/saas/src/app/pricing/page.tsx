import Link from "next/link";
import type { Metadata } from "next";
import { ArrowRight } from "lucide-react";
import { apiPaths } from "@/lib/config";
import { pageMetadata } from "@/lib/seo";
import { formatPlanPrice, resolvePlanDisplayAmount } from "@/lib/billing-providers";
import type { Plan } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/misc";
import { MarketingHeader } from "@/components/marketing/site-header";
import { MarketingFooter } from "@/components/marketing/site-footer";

export const metadata: Metadata = pageMetadata({
  title: "Pricing",
  description:
    "THTWAAT AI agent platform pricing — usage-based plans with the agents, messages, and team limits attached to each one.",
  path: "/pricing"
});

// Plan data changes when an admin updates pricing — always fetch fresh
// rather than baking prices into a static build.
export const dynamic = "force-dynamic";

/**
 * `/payments/plans/` is a public, unauthenticated endpoint (see
 * app/auth/public_endpoints.py) that returns only active plans — safe to
 * call from a server component with no user session.
 */
async function getPlans(): Promise<{ plans: Plan[] | null; error: boolean }> {
  try {
    const res = await fetch(`${apiPaths.v1}/payments/plans/`, { cache: "no-store" });
    if (!res.ok) return { plans: null, error: true };
    const plans = (await res.json()) as Plan[];
    return { plans, error: false };
  } catch {
    return { plans: null, error: true };
  }
}

function planLimits(plan: Plan): string[] {
  const limits: string[] = [];
  if (plan.max_agents != null) limits.push(`${plan.max_agents} agent${plan.max_agents === 1 ? "" : "s"}`);
  if (plan.max_messages != null) limits.push(`${plan.max_messages.toLocaleString()} messages / mo`);
  if (plan.max_team_members != null) limits.push(`${plan.max_team_members} team member${plan.max_team_members === 1 ? "" : "s"}`);
  if (plan.max_domains != null) limits.push(`${plan.max_domains} custom domain${plan.max_domains === 1 ? "" : "s"}`);
  return limits;
}

export default async function PricingPage() {
  const { plans, error } = await getPlans();

  return (
    <main className="min-h-screen bg-canvas">
      <MarketingHeader />

      <section className="mx-auto max-w-4xl px-5 py-16 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Usage-based pricing for the AI agent platform.
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-muted">
          Plans below are pulled live from THTWAAT — the same catalog shown in the workspace
          billing settings. See the full capability list on the{" "}
          <Link href="/platform" className="font-medium text-brand hover:underline">
            platform page
          </Link>
          .
        </p>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-16">
        {error && (
          <>
            <EmptyState
              title="Pricing is temporarily unavailable"
              description="We couldn't reach the billing service just now — please try again shortly, or create a workspace to see current plans."
            />
            <div className="mt-4 flex justify-center">
              <Link href="/signup">
                <Button size="sm">Create workspace</Button>
              </Link>
            </div>
          </>
        )}

        {!error && plans && plans.length === 0 && (
          <EmptyState
            title="No plans are published yet"
            description="Check back soon, or create a workspace and pricing will be shown during setup."
          />
        )}

        {!error && plans && plans.length > 0 && (
          <div className="grid gap-4 md:grid-cols-3">
            {plans.map((plan) => {
              const currency = (plan.display_currency || plan.currency || "USD").toUpperCase();
              const price = resolvePlanDisplayAmount(plan, currency);
              const custom = Boolean(plan.is_custom_pricing);
              const limits = planLimits(plan);
              return (
                <Card key={plan.id}>
                  <h3 className="text-lg font-semibold text-ink">{plan.name}</h3>
                  {plan.description && <p className="mt-1 text-sm text-muted">{plan.description}</p>}
                  <p className="my-4 text-3xl font-semibold text-ink">
                    {custom ? "Custom" : formatPlanPrice(price, currency)}
                    {!custom && (
                      <span className="text-sm font-normal text-muted">/{plan.interval || "month"}</span>
                    )}
                  </p>
                  {limits.length > 0 && (
                    <ul className="mb-4 space-y-1.5 text-sm text-muted">
                      {limits.map((limit) => (
                        <li key={limit}>{limit}</li>
                      ))}
                    </ul>
                  )}
                  {plan.features && plan.features.length > 0 && (
                    <ul className="mb-4 space-y-1.5 text-sm text-ink">
                      {plan.features.map((feature) => (
                        <li key={String(feature)}>{String(feature)}</li>
                      ))}
                    </ul>
                  )}
                  {custom ? (
                    <p className="text-sm text-muted">
                      Create a workspace and reach out from your dashboard to set up custom pricing.
                    </p>
                  ) : (
                    <Link href="/signup">
                      <Button className="w-full">Choose {plan.name}</Button>
                    </Link>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <section className="border-t border-line py-16 text-center">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            See the full platform
          </h2>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/platform">
              <Button size="lg" variant="secondary">
                View the platform <ArrowRight size={16} />
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="lg">Create workspace</Button>
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
