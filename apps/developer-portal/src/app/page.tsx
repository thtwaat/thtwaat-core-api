import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Code2,
  Download,
  Sparkles,
  Terminal,
  Webhook
} from "lucide-react";
import { HomeTrafficCard } from "@/components/home-traffic-card";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/card";
import { site } from "@/lib/config";

const features = [
  {
    icon: BookOpen,
    title: "Guides & SDKs",
    body: "Quick start, auth, JavaScript / REST / Widget SDKs, webhooks, errors, and rate limits.",
    href: "/docs/quick-start"
  },
  {
    icon: Terminal,
    title: "API Explorer",
    body: "Browse the OpenAPI spec, try endpoints, and copy cURL / JS / Python / Node snippets.",
    href: "/api-explorer"
  },
  {
    icon: Download,
    title: "Downloads",
    body: "OpenAPI JSON & YAML, Postman collection, and SDK package links.",
    href: "/downloads"
  },
  {
    icon: Code2,
    title: "Integration examples",
    body: "Website, Landing, SaaS, React, Next.js, Node, Express, and FastAPI recipes.",
    href: "/examples"
  }
];

export default function HomePage() {
  return (
    <div className="space-y-12">
      <section className="relative overflow-hidden rounded-3xl border border-line bg-panel p-8 shadow-soft sm:p-12">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgb(var(--brand-soft)/0.7),transparent_55%)]" />
        <div className="relative grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div>
            <Badge tone="brand">
              <Sparkles size={12} className="mr-1 inline" /> Platform v{site.version}
            </Badge>
            <h1 className="mt-4 font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
              Build AI products on THTWAAT
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-muted">{site.description}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/docs/quick-start">
                <Button size="lg">
                  Quick Start <ArrowRight size={16} />
                </Button>
              </Link>
              <Link href="/api-explorer">
                <Button size="lg" variant="secondary">
                  Open API Explorer
                </Button>
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted">API base: {site.apiUrl}</p>
          </div>
          <HomeTrafficCard />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {features.map(({ icon: Icon, title, body, href }) => (
          <Link key={href} href={href}>
            <Card className="h-full transition hover:border-brand/40">
              <Icon className="text-brand" size={20} />
              <h2 className="mt-3 text-lg font-semibold">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
            </Card>
          </Link>
        ))}
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <Webhook className="text-brand" size={18} />
          <h3 className="mt-3 font-semibold">Webhooks</h3>
          <p className="mt-2 text-sm text-muted">Subscribe to billing, domain, and agent lifecycle events.</p>
          <Link href="/docs/webhooks" className="mt-4 inline-flex text-sm font-semibold text-brand">
            Read guide →
          </Link>
        </Card>
        <Card>
          <Terminal className="text-brand" size={18} />
          <h3 className="mt-3 font-semibold">109 OpenAPI paths</h3>
          <p className="mt-2 text-sm text-muted">Auth, agents, knowledge, marketplace, domains, billing, and more.</p>
          <Link href="/downloads" className="mt-4 inline-flex text-sm font-semibold text-brand">
            Download specs →
          </Link>
        </Card>
        <Card>
          <Code2 className="text-brand" size={18} />
          <h3 className="mt-3 font-semibold">Need help?</h3>
          <p className="mt-2 text-sm text-muted">Search docs or contact support for production integrations.</p>
          <Link href="/support" className="mt-4 inline-flex text-sm font-semibold text-brand">
            Support →
          </Link>
        </Card>
      </section>
    </div>
  );
}
