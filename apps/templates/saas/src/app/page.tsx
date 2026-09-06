import Link from "next/link";
import {
  ArrowRight,
  Bot,
  BookOpen,
  CheckCircle2,
  CreditCard,
  Globe2,
  MessageSquare,
  Phone,
  ShieldCheck,
  Sparkles,
  Store,
  Webhook
} from "lucide-react";
import { site } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const capabilities = [
  {
    icon: Bot,
    title: "AI Agents",
    description: "Configure model, tools, and behavior per agent, then publish or clone in a click."
  },
  {
    icon: MessageSquare,
    title: "AI Chat",
    description: "An embeddable chat widget with a shared inbox for every conversation your agents have."
  },
  {
    icon: Phone,
    title: "Voice / Calling",
    description: "Give an agent a phone number, a greeting, and a human handoff line for real calls."
  },
  {
    icon: BookOpen,
    title: "Knowledge",
    description: "Upload documents into knowledge bases and attach them to any agent for grounded answers."
  },
  {
    icon: Webhook,
    title: "Integrations",
    description: "API keys and webhooks push agent, billing, and domain events into your own systems."
  },
  {
    icon: Globe2,
    title: "Deployment / Custom Domains",
    description: "Connect a custom domain and provision SSL without leaving the dashboard."
  },
  {
    icon: Store,
    title: "Marketplace / Templates",
    description: "Install a prebuilt template or describe your product and have it provisioned for you."
  }
];

const steps = [
  {
    title: "Create your workspace",
    description: "Sign up and get a company workspace provisioned instantly — no backend to stand up."
  },
  {
    title: "Build or generate an agent",
    description: "Configure an agent by hand, or describe your product and let the generator provision it."
  },
  {
    title: "Connect knowledge & channels",
    description: "Attach a knowledge base, then turn on chat, voice calling, or both for that agent."
  },
  {
    title: "Publish",
    description: "Embed the widget, connect a custom domain with SSL, and go live."
  }
];

const values = [
  { icon: ShieldCheck, text: "JWT + OTP authentication out of the box" },
  { icon: CreditCard, text: "Usage tracking and billing, with Stripe and Razorpay checkout" },
  { icon: Globe2, text: "Custom domains with automatic SSL provisioning" },
  { icon: Webhook, text: "Webhooks and API keys for connecting your own systems" }
];

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

      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <p className="text-lg font-semibold text-ink">{site.name}</p>
        <div className="flex gap-3">
          <Link href="/login">
            <Button variant="secondary">Sign in</Button>
          </Link>
          <Link href="/signup">
            <Button>Start free</Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto grid max-w-6xl gap-10 px-5 py-16 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-brand-soft px-3 py-1 text-xs font-semibold text-brand-dark">
            <Sparkles size={14} /> AI SaaS platform
          </p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
            {site.tagline}.
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
          <h2 className="text-3xl font-semibold tracking-tight text-ink">Everything an AI product needs</h2>
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
          <h2 className="text-3xl font-semibold tracking-tight text-ink">How it works</h2>
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
            <h2 className="text-3xl font-semibold tracking-tight text-ink">Built on production infrastructure</h2>
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

      {/* Pricing CTA */}
      <section className="border-y border-line bg-panel py-16">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-5 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-ink">Usage-based billing</h2>
            <p className="mt-2 max-w-xl text-muted">
              Plans, invoices, and checkout live in your workspace billing settings once you're signed in.
            </p>
          </div>
          <Link href="/app/billing">
            <Button size="lg">
              View plans &amp; billing <ArrowRight size={16} />
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

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>
            &copy; {new Date().getFullYear()} {site.name}
          </p>
          <div className="flex flex-wrap gap-5">
            <Link href="/login" className="hover:text-ink">
              Sign in
            </Link>
            <Link href="/signup" className="hover:text-ink">
              Create workspace
            </Link>
            <a href={site.developerPortalUrl} className="hover:text-ink">
              Developer docs
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
