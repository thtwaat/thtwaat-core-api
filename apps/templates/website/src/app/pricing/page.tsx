import { Check } from "lucide-react";
import { Card, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Pricing",
  description: "Simple pricing for AI websites.",
  path: "/pricing",
});

const plans = [
  {
    name: "Starter",
    price: "$49",
    blurb: "For landing sites",
    features: ["1 agent", "5k messages", "Widget embed", "Email leads"],
  },
  {
    name: "Pro",
    price: "$149",
    blurb: "For growing teams",
    features: ["25 agents", "50k messages", "Knowledge search", "Custom domain"],
    highlight: true,
  },
  {
    name: "Business",
    price: "$399",
    blurb: "For multi-brand ops",
    features: ["100 agents", "SSO-ready", "Priority support", "Usage analytics"],
  },
];

export default function PricingPage() {
  return (
    <section className="container-page section space-y-10">
      <div className="mx-auto max-w-2xl text-center space-y-3">
        <h1 className="font-display text-4xl">Pricing</h1>
        <p className="text-ink-muted">Mirror your THTWAAT plan limits — upgrade anytime in the billing portal.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        {plans.map((p) => (
          <Card key={p.name} className={p.highlight ? "ring-2 ring-brand" : ""}>
            {p.highlight && <Badge>Popular</Badge>}
            <h2 className="mt-2 font-display text-2xl">{p.name}</h2>
            <p className="text-sm text-ink-muted">{p.blurb}</p>
            <p className="my-4 font-display text-4xl">
              {p.price}
              <span className="text-base text-ink-muted">/mo</span>
            </p>
            <ul className="mb-6 space-y-2 text-sm">
              {p.features.map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-brand" /> {f}
                </li>
              ))}
            </ul>
            <Link href="/contact">
              <Button className="w-full" variant={p.highlight ? "default" : "secondary"}>
                Get started
              </Button>
            </Link>
          </Card>
        ))}
      </div>
    </section>
  );
}
