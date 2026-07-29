"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowUp, Search, Sparkles } from "lucide-react";
import { site } from "@/lib/config";

type Message = { role: "user" | "assistant"; content: string };
type KnowledgeResult = { document_name?: string; text: string };

export function InlineAssistant() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Tell me what you want to improve. I’ll point you to the fastest path." }
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [knowledge, setKnowledge] = useState<KnowledgeResult[]>([]);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setMessages((old) => [
      ...old,
      { role: "user", content: message },
      { role: "assistant", content: "" }
    ]);

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId })
      });
      if (!response.ok || !response.body) throw new Error("Assistant is temporarily unavailable.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const raw of events) {
          const event = raw.match(/^event:\s*(.+)$/m)?.[1] || "message";
          const data = raw.match(/^data:\s*(.+)$/m)?.[1];
          if (!data) continue;
          const parsed = JSON.parse(data);
          if (event === "token") {
            answer += parsed.text || "";
            setMessages((old) => {
              const copy = [...old];
              copy[copy.length - 1] = { role: "assistant", content: answer };
              return copy;
            });
          }
          if (event === "done") {
            setSessionId(parsed.conversation_id);
            if (!answer && parsed.reply) {
              answer = parsed.reply;
              setMessages((old) => {
                const copy = [...old];
                copy[copy.length - 1] = { role: "assistant", content: answer };
                return copy;
              });
            }
          }
        }
      }
    } catch (error) {
      setMessages((old) => {
        const copy = [...old];
        copy[copy.length - 1] = {
          role: "assistant",
          content: error instanceof Error ? error.message : "Please try again."
        };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  async function searchKnowledge(question: string) {
    if (!question.trim()) return;
    const response = await fetch(`/api/knowledge?q=${encodeURIComponent(question)}`);
    const data = await response.json();
    setKnowledge(data.results || []);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <div className="card overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-ink/10 px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-mint text-brand">
            <Sparkles size={17} />
          </span>
          <div>
            <p className="text-sm font-semibold">Ask {site.name}</p>
            <p className="text-xs text-muted">Live · knowledge-aware</p>
          </div>
        </div>
        <span className="flex items-center gap-1 text-xs text-brand">
          <i className="h-2 w-2 rounded-full bg-brand" /> Online
        </span>
      </div>

      <div className="h-72 space-y-3 overflow-y-auto p-5">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              message.role === "user"
                ? "ml-auto bg-brand text-white"
                : "bg-cream text-ink"
            }`}
          >
            {message.content || "Thinking…"}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      {messages.length === 1 && (
        <div className="flex flex-wrap gap-2 px-5 pb-4">
          {site.suggestedQuestions.slice(0, 3).map((question) => (
            <button
              key={question}
              onClick={() => void send(question)}
              className="rounded-full border border-brand/20 px-3 py-1.5 text-xs text-brand hover:bg-mint"
            >
              {question}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="flex gap-2 border-t border-ink/10 p-3">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about product, pricing, or setup…"
          className="min-w-0 flex-1 rounded-full bg-cream px-4 text-sm outline-none ring-brand focus:ring-2"
        />
        <button
          type="button"
          title="Search knowledge"
          onClick={() => void searchKnowledge(input)}
          className="grid h-11 w-11 place-items-center rounded-full border border-ink/10"
        >
          <Search size={17} />
        </button>
        <button
          type="submit"
          disabled={busy}
          className="grid h-11 w-11 place-items-center rounded-full bg-brand text-white disabled:opacity-50"
        >
          <ArrowUp size={18} />
        </button>
      </form>

      {knowledge.length > 0 && (
        <div className="border-t border-ink/10 bg-mint/50 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-brand">
            Knowledge results
          </p>
          {knowledge.map((result, index) => (
            <p key={index} className="mb-2 text-xs text-muted">
              {result.document_name && <b>{result.document_name}: </b>}
              {result.text}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
