import { AiChatPanel } from "@/components/ai/ai-chat-panel";
import { KnowledgeSearch } from "@/components/ai/knowledge-search";
import { buildMetadata } from "@/lib/seo";

export const metadata = buildMetadata({
  title: "AI Chat",
  description: "Full-page streaming AI chat powered by THTWAAT.",
  path: "/chat",
});

export default function ChatPage() {
  return (
    <section className="container-page section grid gap-8 lg:grid-cols-5">
      <div className="lg:col-span-3 space-y-4">
        <h1 className="font-display text-4xl">AI Chat</h1>
        <p className="text-ink-muted">Streaming responses with suggested questions and session memory.</p>
        <AiChatPanel className="h-[min(75vh,720px)]" />
      </div>
      <div className="lg:col-span-2">
        <KnowledgeSearch />
      </div>
    </section>
  );
}
