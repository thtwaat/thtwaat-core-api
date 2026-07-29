import { buildMetadata } from "@/lib/seo";
import { Card } from "@/components/ui/card";

export const metadata = buildMetadata({
  title: "About",
  description: "About the THTWAAT AI Website Starter Template.",
  path: "/about",
});

export default function AboutPage() {
  return (
    <section className="container-page section max-w-3xl space-y-6">
      <h1 className="font-display text-4xl">About</h1>
      <p className="text-lg text-ink-muted">
        This starter ships a production marketing site wired to the THTWAAT AI Platform —
        publish an agent, drop in your API key, and go live.
      </p>
      <Card className="space-y-3 text-sm text-ink-muted">
        <p>Built for agencies and SaaS teams who need:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Brandable pages with Tailwind + Shadcn-style UI</li>
          <li>Embedded AI that answers from your knowledge base</li>
          <li>Lead capture without a separate CRM setup</li>
          <li>SEO defaults that pass Lighthouse basics</li>
        </ul>
      </Card>
    </section>
  );
}
