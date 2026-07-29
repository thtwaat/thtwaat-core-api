import { Bot, Globe, LineChart, MessagesSquare } from "lucide-react";
import { Card } from "@/components/ui/card";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Services",
  description: "AI website services powered by THTWAAT.",
  path: "/services",
});

const services = [
  { icon: MessagesSquare, title: "Conversational sites", body: "Chat that knows your product docs and pricing." },
  { icon: Globe, title: "Custom domains", body: "Connect brand domains with SSL via THTWAAT Domain Manager." },
  { icon: Bot, title: "Agent publishing", body: "Publish once — embed widget, SDK, or REST anywhere." },
  { icon: LineChart, title: "Usage & billing", body: "Metered AI usage tied to subscription plans." },
];

export default function ServicesPage() {
  return (
    <section className="container-page section space-y-10">
      <div className="max-w-2xl space-y-3">
        <h1 className="font-display text-4xl">Services</h1>
        <p className="text-ink-muted">Everything you need to launch an AI-native marketing presence.</p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2">
        {services.map((s) => (
          <Card key={s.title}>
            <s.icon className="mb-3 h-6 w-6 text-brand" />
            <h2 className="mb-2 font-display text-xl">{s.title}</h2>
            <p className="text-sm text-ink-muted">{s.body}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
