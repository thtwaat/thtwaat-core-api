import Link from "next/link";
import { ArrowRight, Bot, Layers, Shield, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, Badge } from "@/components/ui/card";
import { AiChatPanel } from "@/components/ai/ai-chat-panel";
import { LeadForm } from "@/components/leads/lead-form";
import { siteConfig } from "@/lib/config";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({ path: "/" });

export default function HomePage() {
  return (
    <>
      <section className="container-page section grid items-center gap-12 lg:grid-cols-2">
        <div className="space-y-6">
          <Badge>AI Website Starter</Badge>
          <h1 className="font-display text-4xl leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            {siteConfig.name}
            <span className="gradient-text block">built for conversion</span>
          </h1>
          <p className="max-w-xl text-lg text-ink-muted">{siteConfig.description}</p>
          <div className="flex flex-wrap gap-3">
            <Link href="/chat">
              <Button size="lg">
                Open AI Chat <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/contact">
              <Button size="lg" variant="secondary">
                Book a demo
              </Button>
            </Link>
          </div>
          <p className="text-xs text-ink-muted">
            Connect with `NEXT_PUBLIC_API_URL` + `NEXT_PUBLIC_AGENT_API_KEY` — floating widget loads automatically.
          </p>
        </div>
        <AiChatPanel />
      </section>

      <section className="container-page section grid gap-6 md:grid-cols-3">
        {[
          { icon: Bot, title: "AI chat + widget", body: "Streaming chat, suggestions, and embeddable widget.js." },
          { icon: Layers, title: "CMS-ready blog", body: "Markdown posts, categories, and search out of the box." },
          { icon: Shield, title: "SEO + leads", body: "Metadata, sitemap, schema.org, and capture forms." },
        ].map((f) => (
          <Card key={f.title}>
            <f.icon className="mb-3 h-6 w-6 text-brand" />
            <h3 className="mb-2 font-display text-xl">{f.title}</h3>
            <p className="text-sm text-ink-muted">{f.body}</p>
          </Card>
        ))}
      </section>

      <section className="container-page section grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <Badge>Leads</Badge>
          <h2 className="font-display text-3xl">Capture demos & quotes</h2>
          <p className="text-ink-muted">
            Contact, newsletter, demo booking, and quote requests — webhook-ready.
          </p>
          <div className="flex items-center gap-2 text-sm text-brand">
            <Zap className="h-4 w-4" /> One-click connect to THTWAAT backend
          </div>
        </div>
        <LeadForm type="demo" />
      </section>
    </>
  );
}
