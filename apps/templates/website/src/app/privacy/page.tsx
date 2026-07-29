import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "Privacy Policy",
  path: "/privacy",
});

export default function PrivacyPage() {
  return (
    <section className="container-page section prose prose-slate max-w-3xl dark:prose-invert">
      <h1>Privacy Policy</h1>
      <p>Last updated: {new Date().toISOString().slice(0, 10)}</p>
      <p>
        We process contact and chat data to provide AI assistance. Do not send sensitive personal
        data in chat unless your agreement allows it. Messages may be sent to the THTWAAT API
        configured via your environment variables.
      </p>
      <h2>Data we collect</h2>
      <ul>
        <li>Lead form submissions (name, email, message)</li>
        <li>Chat transcripts for your published agent</li>
        <li>Basic analytics via your hosting provider</li>
      </ul>
      <h2>Contact</h2>
      <p>Email privacy@thtwaat.com for data requests.</p>
    </section>
  );
}
