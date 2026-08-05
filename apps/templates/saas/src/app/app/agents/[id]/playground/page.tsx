"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { agentsApi, conversationsApi, knowledgeApi } from "@/lib/services";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";

type PlayMsg = { id: string; role: string; content: string };

export default function AgentPlaygroundPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const qc = useQueryClient();
  const [input, setInput] = useState("");
  const [locale, setLocale] = useState("en");
  const [thinking, setThinking] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<PlayMsg[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sources, setSources] = useState<Array<{ document_name?: string; text?: string }>>([]);

  const agent = useQuery({ queryKey: ["agent", id], queryFn: () => agentsApi.get(id) });
  const bases = useQuery({ queryKey: ["kb-bases"], queryFn: knowledgeApi.listBases });

  const createConv = useMutation({
    mutationFn: () =>
      conversationsApi.create({
        agent_id: id,
        title: "Playground",
        channel: "dashboard"
      }),
    onSuccess: (conv) => setConversationId(conv.id)
  });

  const send = useMutation({
    mutationFn: async (content: string) => {
      setThinking("Understanding your message…");
      let cid = conversationId;
      if (!cid) {
        const conv = await conversationsApi.create({
          agent_id: id,
          title: "Playground",
          channel: "dashboard"
        });
        cid = conv.id;
        setConversationId(cid);
      }
      setMsgs((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", content }]);
      setThinking("Searching knowledge…");
      try {
        const firstBase = (bases.data || [])[0];
        if (firstBase?.id) {
          const hit = await knowledgeApi.search(firstBase.id, content);
          const results = (hit as { results?: typeof sources })?.results || [];
          setSources(results.slice(0, 3));
        }
      } catch {
        /* optional */
      }
      setThinking("Thinking…");
      const res = await conversationsApi.sendMessage(cid, content);
      const assistant =
        (res as { assistant_message?: { id?: string; content?: string; role?: string } })
          .assistant_message || null;
      return assistant;
    },
    onSuccess: (assistant) => {
      setThinking(null);
      if (assistant?.content) {
        setMsgs((prev) => [
          ...prev,
          {
            id: String(assistant.id || `a-${Date.now()}`),
            role: "assistant",
            content: String(assistant.content)
          }
        ]);
      }
      void qc.invalidateQueries({ queryKey: ["inbox"] });
    },
    onError: (e: Error) => {
      setThinking(null);
      toast.error(e.message || "Playground send failed");
    }
  });

  const reset = () => {
    setMsgs([]);
    setConversationId(null);
    setSources([]);
    setThinking(null);
    setInput("");
  };

  const status = useMemo(() => {
    if (thinking) return thinking;
    if (send.isPending) return "Generating…";
    return "Ready";
  }, [thinking, send.isPending]);

  if (agent.isLoading) return <p className="text-sm text-muted">Loading playground…</p>;
  if (!agent.data) return <EmptyState title="Agent not found" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Playground · ${agent.data.name}`}
        description="Test conversation memory, knowledge search, and thinking indicators before publish."
        action={
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/app/agents/${id}`}
              className="inline-flex items-center rounded-xl border border-line px-3 py-2 text-sm font-medium"
            >
              Back to agent
            </Link>
            <Button variant="secondary" onClick={reset}>
              New session
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <Card className="flex min-h-[520px] flex-col">
          <CardHeader title="Live chat" action={<Badge tone="neutral">{status}</Badge>} />
          <div className="mb-3 flex flex-wrap items-end gap-3">
            <label className="space-y-1 text-sm">
              <span className="text-xs text-muted">Reply language</span>
              <select
                className="block rounded-lg border border-line bg-white px-2 py-1.5 text-sm"
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
                aria-label="Locale"
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="ar">Arabic</option>
              </select>
            </label>
            {!conversationId ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={createConv.isPending}
                onClick={() => createConv.mutate()}
              >
                Start conversation
              </Button>
            ) : (
              <p className="text-xs text-muted">Session {conversationId.slice(0, 8)}…</p>
            )}
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-line bg-slate-50/60 p-3">
            {!msgs.length && !thinking ? (
              <p className="text-sm text-muted">Send a message to exercise memory + RAG.</p>
            ) : null}
            {msgs.map((m) => (
              <div
                key={m.id}
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "ml-auto bg-teal-800 text-white"
                    : "bg-white text-ink shadow-sm"
                }`}
              >
                {m.content}
              </div>
            ))}
            {thinking ? (
              <div className="inline-flex items-center gap-2 rounded-2xl bg-white px-3 py-2 text-sm text-muted shadow-sm">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-teal-600" />
                {thinking}
              </div>
            ) : null}
          </div>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const text = input.trim();
              if (!text || send.isPending) return;
              setInput("");
              void send.mutate(locale !== "en" ? `[locale:${locale}] ${text}` : text);
            }}
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask the agent…"
              className="min-h-[44px] flex-1"
            />
            <Button type="submit" disabled={send.isPending || !input.trim()}>
              Send
            </Button>
          </form>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Knowledge hits" />
            {!sources.length ? (
              <p className="text-xs text-muted">
                RAG snippets appear here when search returns results.
              </p>
            ) : (
              <ul className="space-y-2 text-xs">
                {sources.map((s, i) => (
                  <li key={i} className="rounded-lg border border-line p-2">
                    <p className="font-medium">{s.document_name || `Source ${i + 1}`}</p>
                    <p className="mt-1 line-clamp-4 text-muted">{s.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <CardHeader title="Capabilities" />
            <ul className="space-y-1 text-sm text-muted">
              <li>Conversation memory (thread replay)</li>
              <li>Knowledge search / RAG</li>
              <li>Thinking indicator</li>
              <li>Multi-language prompt hint</li>
              <li>Knowledge bases: {(bases.data || []).length}</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
