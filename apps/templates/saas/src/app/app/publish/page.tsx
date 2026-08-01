"use client";

import Link from "next/link";
import { CheckCircle2, Link2, Rocket, Shield } from "lucide-react";
import { site } from "@/lib/config";
import { PageHeader } from "@/components/ui/misc";
import { Card, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const steps = [
  {
    icon: Link2,
    title: "Connect",
    body: "Set NEXT_PUBLIC_API_URL, then sign in against the THTWAAT Core API. Create agent API keys in Settings after login — never bake live keys into the frontend.",
    href: "/login",
    cta: "Open login"
  },
  {
    icon: Rocket,
    title: "Deploy",
    body: "Deploy this folder to Vercel or build the included Dockerfile. No backend changes required.",
    href: "/app/agents",
    cta: "Prepare agents"
  },
  {
    icon: Shield,
    title: "Publish",
    body: "Publish an agent, create API keys, embed the widget, and attach a verified domain with SSL.",
    href: "/app/domains",
    cta: "Manage domains"
  }
];

const checklist = [
  "Create company + owner via Signup",
  "Create and publish at least one agent",
  "Upload knowledge documents",
  "Generate widget embed snippet",
  "Add and verify custom domain",
  "Request SSL and confirm LIVE status",
  "Confirm usage meter + billing plan"
];

export default function PublishPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Publish"
        description="One-click connect → deploy → publish flow for this SaaS starter."
      />

      <div className="grid gap-4 md:grid-cols-3">
        {steps.map((step, index) => (
          <Card key={step.title}>
            <Badge tone="brand">Step {index + 1}</Badge>
            <div className="mt-4 grid h-10 w-10 place-items-center rounded-xl bg-brand-soft text-brand">
              <step.icon size={18} />
            </div>
            <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
            <p className="mt-2 text-sm text-muted">{step.body}</p>
            <Link href={step.href} className="mt-4 inline-block">
              <Button size="sm">{step.cta}</Button>
            </Link>
          </Card>
        ))}
      </div>

      <Card>
        <h3 className="text-lg font-semibold">Go-live checklist</h3>
        <ul className="mt-4 space-y-3">
          {checklist.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-muted">
              <CheckCircle2 className="mt-0.5 text-brand" size={16} />
              {item}
            </li>
          ))}
        </ul>
        <div className="mt-6 rounded-xl bg-canvas p-4 text-sm">
          <p className="font-medium text-ink">Current connection</p>
          <p className="mt-1 text-muted">API: {site.apiUrl}</p>
          <p className="text-muted">
            Agent keys: create and rotate them in Settings after sign-in (never ship live keys in the browser bundle).
          </p>
        </div>
      </Card>
    </div>
  );
}
