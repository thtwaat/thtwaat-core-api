import { LeadForm } from "@/components/leads/lead-form";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Contact",
  description: "Contact, book a demo, or request a quote.",
  path: "/contact",
});

export default function ContactPage() {
  return (
    <section className="container-page section grid gap-10 lg:grid-cols-2">
      <div className="space-y-4">
        <h1 className="font-display text-4xl">Contact</h1>
        <p className="text-ink-muted">
          Tell us about your project. Or use the floating AI widget for instant answers.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <LeadForm type="newsletter" />
          <LeadForm type="quote" />
        </div>
      </div>
      <LeadForm type="contact" />
    </section>
  );
}
