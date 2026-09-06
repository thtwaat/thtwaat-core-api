import Link from "next/link";
import { ArrowRight, CheckCircle2, Sparkles } from "lucide-react";
import { site } from "@/lib/config";
import { capabilities, steps, values } from "@/lib/marketing-content";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { MarketingHeader } from "@/components/marketing/site-header";
import { MarketingFooter } from "@/components/marketing/site-footer";

const templatesCapability = capabilities.find((c) => c.title === "Marketplace / Templates")!;

const faqs = [
  {
    q: "What is THTWAAT?",
    a: "An AI SaaS platform for building and running AI agents — chat, voice calling, knowledge search, custom domains, and billing are wired to the THTWAAT Core API."
  },
  {
    q: "Do I need to build my own backend?",
    a: "No. This dashboard talks directly to the production THTWAAT Core API — auth, agents, knowledge, domains, and billing are already implemented."
  },
  {
    q: "Can my agent make and receive phone calls?",
    a: "Yes. Turning on Calling for an agent lets you set a phone number, a greeting, and an optional human handoff number."
  },
  {
    q: "Can I use my own domain?",
    a: "Yes. Connect a custom domain from the dashboard and SSL is provisioned automatically."
  },
  {
    q: "How does billing work?",
    a: "Usage is tracked per workspace, and checkout is handled through Stripe or Razorpay depending on your billing configuration."
  },
  {
    q: "Can I integrate with my own tools?",
    a: "Yes, via API keys for server-to-server access and webhooks for agent, billing, and domain lifecycle events."
  }
];

export default function MarketingHome() {
  return (
    <main className="min-h-screen bg-canvas">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            name: site.name,
            url: site.url,
            description: site.description,
            applicationCategory: "BusinessApplication",
            operatingSystem: "Web"
          })
        }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Organization",
            name: site.name,
            url: site.url,
            logo: `${site.url}/opengraph-image`
          })
        }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebSite",
            name: site.name,
            url: site.url
          })
        }}
      />

      <MarketingHeader />

      {/* Hero */}
      <section className="mx-auto grid max-w-6xl gap-10 px-5 py-16 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-brand-soft px-3 py-1 text-xs font-semibold text-brand-dark">
            <Sparkles size={14} /> AI SaaS platform
          </p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
            The AI agent platform for chat, voice, and your whole SaaS.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-muted">{site.description}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/signup">
              <Button size="lg">
                Create workspace <ArrowRight size={16} />
              </Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="secondary">
                Sign in
              </Button>
            </Link>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {capabilities.slice(0, 4).map(({ icon: Icon, title }) => (
            <div key={title} className="rounded-2xl border border-line bg-panel p-5 shadow-soft">
              <Icon className="text-brand" size={20} />
              <p className="mt-3 font-semibold text-ink">{title}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Product capabilities */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">
            Build AI agents for chat, voice calling, and knowledge search
          </h2>
          <p className="mt-3 text-muted">
            Every capability below is available today in the dashboard — nothing here is a roadmap item.
          </p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map(({ icon: Icon, title, description }) => (
            <Card key={title}>
              <Icon className="text-brand" size={20} />
              <h3 className="mt-3 font-semibold text-ink">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-line bg-panel py-16">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-3xl font-semibold tracking-tight text-ink">
            How teams build AI products on THTWAAT
          </h2>
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => (
              <div key={step.title}>
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand-dark">
                  {i + 1}
                </span>
                <h3 className="mt-4 font-semibold text-ink">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature/value */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight text-ink">
              Everything an AI SaaS needs — auth, billing, and custom domains
            </h2>
            <p className="mt-3 max-w-lg text-muted">
              The dashboard is a thin layer over the THTWAAT Core API — the same auth, billing, and
              domain systems back every workspace.
            </p>
          </div>
          <ul className="grid gap-4">
            {values.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 rounded-2xl border border-line bg-panel p-4 shadow-soft">
                <Icon className="mt-0.5 shrink-0 text-brand" size={18} />
                <span className="text-sm text-ink">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Templates / marketplace */}
      <section className="border-y border-line bg-panel py-16">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 lg:grid-cols-2 lg:items-center">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight text-ink">
              Launch faster with prebuilt AI agent templates
            </h2>
            <p className="mt-3 max-w-lg text-muted">{templatesCapability.description}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/platform">
                <Button size="lg" variant="secondary">
                  Explore the platform <ArrowRight size={16} />
                </Button>
              </Link>
              <Link href="/signup">
                <Button size="lg">Start free</Button>
              </Link>
            </div>
          </div>
          <div className="rounded-2xl border border-line bg-canvas p-6 shadow-soft">
            <templatesCapability.icon className="text-brand" size={22} />
            <p className="mt-3 font-semibold text-ink">{templatesCapability.title}</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Install a template into your workspace, or describe your product and let the generator
              provision agents, knowledge bases, and channels for you.
            </p>
          </div>
        </div>
      </section>

      {/* Pricing CTA */}
      <section className="py-16">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-5 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-ink">Usage-based billing</h2>
            <p className="mt-2 max-w-xl text-muted">
              See plans and what's included, then create a workspace to pick one.
            </p>
          </div>
          <Link href="/pricing">
            <Button size="lg">
              View plans &amp; pricing <ArrowRight size={16} />
            </Button>
          </Link>
        </div>
      </section>

      {/* FAQ */}
      <section className="mx-auto max-w-3xl px-5 py-16">
        <h2 className="text-3xl font-semibold tracking-tight text-ink">Frequently asked questions</h2>
        <div className="mt-8 divide-y divide-line">
          {faqs.map(({ q, a }) => (
            <details key={q} className="group py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-ink">
                {q}
                <CheckCircle2
                  size={18}
                  className="shrink-0 text-line transition group-open:text-brand"
                />
              </summary>
              <p className="mt-3 text-sm leading-6 text-muted">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-6xl px-5 py-16 text-center">
        <h2 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Start building your AI product today
        </h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/signup">
            <Button size="lg">
              Create workspace <ArrowRight size={16} />
            </Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="secondary">
              Sign in
            </Button>
          </Link>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
