import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Terms of Service",
  path: "/terms",
});

export default function TermsPage() {
  return (
    <section className="container-page section prose prose-slate max-w-3xl dark:prose-invert">
      <h1>Terms of Service</h1>
      <p>Last updated: {new Date().toISOString().slice(0, 10)}</p>
      <p>
        This starter template is provided as-is for building AI-enabled websites on the THTWAAT
        platform. You are responsible for your content, agent prompts, and compliance with local law.
      </p>
      <h2>Acceptable use</h2>
      <p>Do not use the AI features to generate unlawful, harmful, or infringing content.</p>
      <h2>API usage</h2>
      <p>Usage is subject to your THTWAAT subscription plan limits and fair-use policies.</p>
    </section>
  );
}
