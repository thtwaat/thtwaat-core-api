import {
  ArrowRight,
  Bot,
  Check,
  Clock3,
  Database,
  Globe2,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap
} from "lucide-react";
import { InlineAssistant } from "@/components/inline-assistant";
import { LeadForm } from "@/components/lead-form";
import { AiFaq } from "@/components/ai-faq";
import { PublishStrip } from "@/components/publish-strip";
import { site } from "@/lib/config";

const features = [
  [MessageSquareText, "Streaming AI conversations", "Answer visitors instantly with real-time responses and persistent sessions."],
  [Database, "Knowledge-grounded answers", "Turn product docs, policies, and FAQs into accurate customer guidance."],
  [TrendingUp, "Conversion-ready lead capture", "Move qualified visitors into demo, quote, newsletter, or contact flows."],
  [Globe2, "Publish everywhere", "Use your landing domain, floating widget, JavaScript SDK, or REST API."],
  [ShieldCheck, "Production controls", "Multi-tenant isolation, metering, quotas, SSL, and domain management."],
  [Zap, "Two-variable setup", "Connect with only NEXT_PUBLIC_API_URL and NEXT_PUBLIC_AGENT_API_KEY."]
] as const;

const benefits = [
  ["Respond in seconds", "Give every visitor a useful next step—even outside business hours."],
  ["Qualify before the call", "Let AI discover goals, urgency, and fit before your sales team joins."],
  ["Reduce repetitive support", "Ground answers in your knowledge while keeping humans focused on edge cases."]
];

const testimonials = [
  ["“We replaced three separate landing tools with one page and an assistant that actually knows our offer.”", "Maya R.", "Growth Lead"],
  ["“The suggested questions doubled the number of visitors who started a meaningful conversation.”", "Arjun S.", "SaaS Founder"],
  ["“We launched the first version in an afternoon—not another six-week website project.”", "Elena P.", "Agency Director"]
];

const plans = [
  { name: "Starter", price: "$49", description: "Validate your AI landing experience.", items: ["1 published agent", "5,000 messages", "Lead capture", "Floating widget"] },
  { name: "Pro", price: "$149", description: "Convert traffic across a growing business.", items: ["25 agents", "Knowledge search", "Custom domain", "Usage analytics"], featured: true },
  { name: "Business", price: "$399", description: "Scale across teams, brands, and products.", items: ["100 agents", "Priority support", "Advanced controls", "High-volume usage"] }
];

export default function LandingPage() {
  return (
    <main>
      <header className="sticky top-0 z-40 border-b border-ink/10 bg-cream/85 backdrop-blur-xl">
        <nav className="container-page flex h-16 items-center justify-between">
          <a href="#" className="font-[var(--font-display)] text-xl font-semibold">{site.name}</a>
          <div className="hidden gap-7 text-sm text-muted md:flex">
            <a href="#features">Features</a>
            <a href="#benefits">Benefits</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </div>
          <a href="#book-demo" className="button-primary h-10 px-5">Book demo</a>
        </nav>
      </header>

      <section className="container-page grid min-h-[84vh] items-center gap-12 py-20 lg:grid-cols-[1.05fr_.95fr]">
        <div>
          <span className="eyebrow inline-flex items-center gap-2">
            <Sparkles size={14} /> AI that turns attention into action
          </span>
          <h1 className="mt-5 max-w-3xl font-[var(--font-display)] text-5xl font-semibold leading-[1.02] tracking-[-.04em] sm:text-7xl">
            Your best salesperson is now on every page.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-muted">
            {site.description}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#ai-chat" className="button-primary">Try the AI <ArrowRight size={17} /></a>
            <a href="#book-demo" className="button-secondary">Book a demo</a>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
            <span className="flex items-center gap-2"><Check size={15} className="text-brand" /> No backend changes</span>
            <span className="flex items-center gap-2"><Check size={15} className="text-brand" /> Setup in minutes</span>
            <span className="flex items-center gap-2"><Check size={15} className="text-brand" /> Production-ready</span>
          </div>
        </div>
        <div className="relative">
          <div className="absolute -inset-6 -z-10 rounded-[3rem] bg-gradient-to-br from-mint to-accent/20 blur-2xl" />
          <div className="card space-y-4 p-8">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-full bg-mint text-brand">
                <Bot size={18} />
              </span>
              <div>
                <p className="text-sm font-semibold">{site.name} Assistant</p>
                <p className="text-xs text-muted">Live on every page</p>
              </div>
            </div>
            <div className="space-y-3">
              <div className="ml-auto max-w-[85%] rounded-2xl bg-brand px-4 py-3 text-sm text-white">
                Which plan fits a team of 12?
              </div>
              <div className="max-w-[90%] rounded-2xl bg-cream px-4 py-3 text-sm leading-6 text-ink">
                Pro is usually the sweet spot — knowledge search, custom domain, and room to scale.
              </div>
            </div>
            <a href="#ai-chat" className="button-primary w-full">Start a real conversation</a>
          </div>
        </div>
      </section>

      <section id="ai-chat" className="border-y border-ink/10 bg-white/45">
        <div className="container-page section grid items-center gap-12 lg:grid-cols-[.9fr_1.1fr]">
          <div>
            <p className="eyebrow">AI chat CTA</p>
            <h2 className="mt-3 font-[var(--font-display)] text-4xl font-semibold tracking-tight sm:text-5xl">
              Let visitors ask before they bounce.
            </h2>
            <p className="mt-4 max-w-lg text-muted">
              Streaming answers, suggested questions, and knowledge search — connected to your published
              THTWAAT agent with zero backend changes.
            </p>
            <ul className="mt-8 space-y-3 text-sm text-muted">
              <li className="flex gap-2"><Check size={16} className="text-brand" /> SSE streaming with non-stream fallback</li>
              <li className="flex gap-2"><Check size={16} className="text-brand" /> Floating widget on every page</li>
              <li className="flex gap-2"><Check size={16} className="text-brand" /> Knowledge-aware responses</li>
            </ul>
          </div>
          <InlineAssistant />
        </div>
      </section>

      <section className="border-y border-ink/10 bg-white/45 py-8">
        <div className="container-page flex flex-wrap items-center justify-center gap-x-12 gap-y-4 text-sm text-muted">
          <span>Powered by THTWAAT</span><span>Streaming SSE</span><span>Knowledge-aware</span>
          <span>Custom domains</span><span>Usage-metered</span>
        </div>
      </section>

      <section id="features" className="container-page section">
        <div className="max-w-2xl">
          <p className="eyebrow">Everything connected</p>
          <h2 className="mt-3 font-[var(--font-display)] text-4xl font-semibold tracking-tight sm:text-5xl">
            One focused page. Every conversion tool.
          </h2>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {features.map(([Icon, title, body]) => (
            <article key={title} className="card">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-mint text-brand"><Icon size={20} /></span>
              <h3 className="mt-5 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="benefits" className="bg-ink text-white">
        <div className="container-page section grid gap-14 lg:grid-cols-2">
          <div>
            <p className="eyebrow text-mint">Built for outcomes</p>
            <h2 className="mt-3 font-[var(--font-display)] text-4xl font-semibold sm:text-5xl">
              More useful conversations. Less friction.
            </h2>
            <p className="mt-5 max-w-lg text-white/65">
              Make your landing page answer, qualify, and route demand instead of only describing your product.
            </p>
          </div>
          <div className="grid gap-4">
            {benefits.map(([title, body], index) => (
              <div key={title} className="rounded-3xl border border-white/10 p-6">
                <p className="text-xs text-accent">0{index + 1}</p>
                <h3 className="mt-2 text-xl font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/60">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="container-page section">
        <div className="text-center">
          <p className="eyebrow">Simple pricing</p>
          <h2 className="mt-3 font-[var(--font-display)] text-4xl font-semibold sm:text-5xl">Start focused. Scale when it works.</h2>
        </div>
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {plans.map((plan) => (
            <article key={plan.name} className={`card relative ${plan.featured ? "border-brand bg-mint/60" : ""}`}>
              {plan.featured && <span className="absolute right-5 top-5 rounded-full bg-brand px-3 py-1 text-xs text-white">Most popular</span>}
              <h3 className="text-xl font-semibold">{plan.name}</h3>
              <p className="mt-2 text-sm text-muted">{plan.description}</p>
              <p className="my-6 font-[var(--font-display)] text-5xl font-semibold">{plan.price}<small className="text-base font-normal text-muted">/mo</small></p>
              <ul className="space-y-3 text-sm">
                {plan.items.map((item) => <li key={item} className="flex gap-2"><Check size={16} className="text-brand" /> {item}</li>)}
              </ul>
              <a href="#book-demo" className={`mt-8 w-full ${plan.featured ? "button-primary" : "button-secondary"}`}>Choose {plan.name}</a>
            </article>
          ))}
        </div>
      </section>

      <section className="bg-white/50">
        <div className="container-page section">
          <p className="eyebrow">What teams say</p>
          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            {testimonials.map(([quote, name, role]) => (
              <figure key={name} className="card">
                <blockquote className="font-[var(--font-display)] text-xl leading-8">{quote}</blockquote>
                <figcaption className="mt-6 text-sm"><b>{name}</b><span className="block text-muted">{role}</span></figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <PublishStrip />

      <section id="faq" className="container-page section grid gap-12 lg:grid-cols-[.75fr_1.25fr]">
        <div>
          <p className="eyebrow">AI-powered FAQ</p>
          <h2 className="mt-3 font-[var(--font-display)] text-4xl font-semibold">Questions before the conversation?</h2>
          <p className="mt-4 text-muted">Open an answer or send the exact question to the floating AI assistant.</p>
        </div>
        <AiFaq />
      </section>

      <section id="book-demo" className="container-page pb-24">
        <div className="overflow-hidden rounded-[2.5rem] bg-brand text-white">
          <div className="grid gap-10 p-7 sm:p-12 lg:grid-cols-2">
            <div>
              <p className="eyebrow text-mint">Book a demo</p>
              <h2 className="mt-3 font-[var(--font-display)] text-4xl font-semibold">See your own AI experience in action.</h2>
              <p className="mt-4 text-white/70">Bring your website and top questions. We’ll show you the path from visitor to qualified lead.</p>
              <div className="mt-8 space-y-3 text-sm text-white/75">
                <p className="flex gap-2"><Clock3 size={17} /> 30-minute working session</p>
                <p className="flex gap-2"><Bot size={17} /> Personalized agent walkthrough</p>
              </div>
            </div>
            <div className="rounded-3xl bg-cream p-6 text-ink"><LeadForm type="demo" /></div>
          </div>
        </div>
      </section>

      <section id="contact" className="container-page pb-24">
        <div className="grid gap-8 lg:grid-cols-3">
          <div className="card lg:col-span-1">
            <p className="eyebrow">Contact</p>
            <h2 className="my-3 font-[var(--font-display)] text-3xl font-semibold">Talk to our team.</h2>
            <p className="mb-6 text-sm text-muted">Questions about rollout, security, or pricing? We’ll reply quickly.</p>
            <LeadForm type="contact" />
          </div>
          <div className="card">
            <p className="eyebrow">Request a quote</p>
            <h2 className="my-3 font-[var(--font-display)] text-3xl font-semibold">Need a tailored rollout?</h2>
            <LeadForm type="quote" />
          </div>
          <div className="card">
            <p className="eyebrow">Stay in the loop</p>
            <h2 className="my-3 font-[var(--font-display)] text-3xl font-semibold">Practical AI conversion ideas.</h2>
            <p className="mb-6 text-sm text-muted">A concise monthly note. No noise.</p>
            <LeadForm type="newsletter" compact />
          </div>
        </div>
      </section>

      <footer className="border-t border-ink/10">
        <div className="container-page grid gap-8 py-12 md:grid-cols-3">
          <div><p className="font-[var(--font-display)] text-xl font-semibold">{site.name}</p><p className="mt-2 text-sm text-muted">{site.description}</p></div>
          <div className="flex flex-wrap content-start gap-x-5 gap-y-2 text-sm text-muted">
            <a href="#features">Features</a><a href="#pricing">Pricing</a><a href="#publish">Publish</a><a href="#faq">FAQ</a><a href="#contact">Contact</a>
          </div>
          <p className="text-sm text-muted md:text-right">© {new Date().getFullYear()} {site.name}<br />Powered by THTWAAT AI</p>
        </div>
      </footer>
    </main>
  );
}
