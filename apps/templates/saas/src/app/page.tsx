import Link from "next/link";
import { ArrowRight, Bot, Globe2, ShieldCheck, Sparkles } from "lucide-react";
import { site } from "@/lib/config";
import { Button } from "@/components/ui/button";

export default function MarketingHome() {
  return (
    <main className="min-h-screen bg-canvas">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <p className="text-lg font-semibold">{site.name}</p>
        <div className="flex gap-3">
          <Link href="/login"><Button variant="secondary">Sign in</Button></Link>
          <Link href="/signup"><Button>Start free</Button></Link>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-10 px-5 py-16 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-brand-soft px-3 py-1 text-xs font-semibold text-brand-dark">
            <Sparkles size={14} /> Zero backend changes
          </p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
            Ship your AI SaaS on the THTWAAT platform.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-muted">
            Auth, agents, knowledge, domains, billing, usage, and publish flows — wired to production APIs with only two env vars.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/signup"><Button size="lg">Create workspace <ArrowRight size={16} /></Button></Link>
            <Link href="/app"><Button size="lg" variant="secondary">Open dashboard</Button></Link>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            [Bot, "Agents & publish"],
            [Globe2, "Domains + SSL"],
            [ShieldCheck, "JWT + OTP auth"],
            [Sparkles, "Usage & billing"]
          ].map(([Icon, label]) => (
            <div key={String(label)} className="rounded-2xl border border-line bg-panel p-5 shadow-soft">
              <Icon className="text-brand" size={20} />
              <p className="mt-3 font-semibold">{label as string}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
