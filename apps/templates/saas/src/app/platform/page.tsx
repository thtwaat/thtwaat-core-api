import Link from "next/link";
import type { Metadata } from "next";
import { ArrowRight } from "lucide-react";
import { site } from "@/lib/config";
import { pageMetadata } from "@/lib/seo";
import { capabilities, values } from "@/lib/marketing-content";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { MarketingHeader } from "@/components/marketing/site-header";
import { MarketingFooter } from "@/components/marketing/site-footer";

export const metadata: Metadata = pageMetadata({
  title: "AI Agent Platform — Chat, Voice & Knowledge Agents",
  description:
    "THTWAAT is an AI agent platform for building agents with chat, voice calling, and knowledge search — backed by auth, billing, and custom domains.",
  path: "/platform"
});

export default function PlatformPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <MarketingHeader />

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-5 py-16 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Everything your AI agent platform needs, in one place.
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-muted">
          Chat, voice calling, and knowledge search for your agents — plus the auth, billing, and
          custom domains an AI SaaS product needs around them. All of it runs on the production
          THTWAAT Core API, the same{" "}
          <a href={site.developerPortalUrl} className="font-medium text-brand hover:underline">
            REST API documented in the developer portal
          </a>
          .
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/signup">
            <Button size="lg">
              Create workspace <ArrowRight size={16} />
            </Button>
          </Link>
          <Link href="/pricing">
            <Button size="lg" variant="secondary">
              View pricing
            </Button>
          </Link>
        </div>
      </section>

      {/* Capabilities */}
      <section className="border-y border-line bg-panel py-16">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">Every capability, in one platform</h2>
          <p className="mt-3 max-w-2xl text-muted">
            Each capability below ships in the product today — there's no separate add-on to enable.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map(({ icon: Icon, title, description }) => (
              <Card key={title}>
                <Icon className="text-brand" size={20} />
                <h3 className="mt-3 font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Infrastructure */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight text-ink">Production infrastructure included</h2>
            <p className="mt-3 max-w-lg text-muted">
              The dashboard is a thin layer over the THTWAAT Core API — the same auth, billing, and
              domain systems back every workspace on the platform.
            </p>
          </div>
          <ul className="grid gap-4">
            {values.map(({ icon: Icon, text }) => (
              <li
                key={text}
                className="flex items-start gap-3 rounded-2xl border border-line bg-panel p-4 shadow-soft"
              >
                <Icon className="mt-0.5 shrink-0 text-brand" size={18} />
                <span className="text-sm text-ink">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-line py-16 text-center">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            See what a workspace costs
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-muted">
            Usage-based plans, with the limits and features attached to each one.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/pricing">
              <Button size="lg">
                View plans &amp; pricing <ArrowRight size={16} />
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="lg" variant="secondary">
                Create workspace
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
