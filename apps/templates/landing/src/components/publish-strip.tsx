import { Link2, Rocket, Shield } from "lucide-react";
import { Badge, Card } from "@/components/ui/card";

const steps = [
  {
    icon: Link2,
    title: "Connect",
    body: "Publish your THTWAAT agent and paste two env vars — API URL and agent API key."
  },
  {
    icon: Rocket,
    title: "Deploy",
    body: "Import to Vercel or build the included Dockerfile. No backend changes required."
  },
  {
    icon: Shield,
    title: "Publish",
    body: "Verify your domain in THTWAAT Domain Manager, request SSL, and go live."
  }
] as const;

export function PublishStrip() {
  return (
    <section id="publish" className="container-page section">
      <div className="mx-auto max-w-2xl text-center">
        <Badge>One-click ready</Badge>
        <h2 className="mt-4 font-[var(--font-display)] text-4xl font-semibold tracking-tight sm:text-5xl">
          Connect. Deploy. Publish.
        </h2>
        <p className="mt-4 text-muted">
          Ship a conversion-focused landing page on your stack in minutes — wired to the same
          public chat, widget, and lead APIs you already use.
        </p>
      </div>
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {steps.map((step, index) => (
          <Card key={step.title} className="relative">
            <span className="text-xs font-semibold text-accent">Step {index + 1}</span>
            <span className="mt-4 grid h-11 w-11 place-items-center rounded-2xl bg-mint text-brand">
              <step.icon size={20} />
            </span>
            <h3 className="mt-5 text-lg font-semibold">{step.title}</h3>
            <p className="mt-2 text-sm leading-6 text-muted">{step.body}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
