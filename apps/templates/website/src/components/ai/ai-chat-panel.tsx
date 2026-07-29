"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { siteConfig } from "@/lib/config";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; content: string };

export function AiChatPanel({
  className,
  showSuggestions = true,
}: {
  className?: string;
  showSuggestions?: boolean;
}) {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content: `Welcome to ${siteConfig.name}. Ask about products, pricing, or book a demo.`,
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId }),
      });

      if (!res.ok || !res.body) {
        const fallback = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, session_id: sessionId }),
        });
        const data = await fallback.json();
        if (data.conversation_id) setSessionId(data.conversation_id);
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: data.reply || data.error || "Something went wrong.",
          };
          return copy;
        });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistant = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const lines = part.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!data) continue;
          try {
            const parsed = JSON.parse(data);
            if (event === "token") {
              assistant += parsed.text || "";
              setMessages((m) => {
                const copy = [...m];
                copy[copy.length - 1] = { role: "assistant", content: assistant };
                return copy;
              });
            }
            if (event === "done" && parsed.conversation_id) {
              setSessionId(parsed.conversation_id);
              if (parsed.reply && !assistant) {
                assistant = parsed.reply;
                setMessages((m) => {
                  const copy = [...m];
                  copy[copy.length - 1] = { role: "assistant", content: assistant };
                  return copy;
                });
              }
            }
            if (event === "error") {
              setMessages((m) => {
                const copy = [...m];
                copy[copy.length - 1] = {
                  role: "assistant",
                  content: parsed.message || "Stream error",
                };
                return copy;
              });
            }
          } catch {
            /* ignore partial JSON */
          }
        }
      }
    } catch (err) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          content: err instanceof Error ? err.message : "Network error",
        };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <Card className={cn("flex h-[min(70vh,640px)] flex-col p-0 overflow-hidden", className)}>
      <div className="flex items-center gap-2 border-b border-black/5 px-4 py-3">
        <Sparkles className="h-4 w-4 text-brand" />
        <div>
          <p className="text-sm font-semibold">AI Assistant</p>
          <p className="text-xs text-ink-muted">Streaming · Knowledge-aware</p>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={cn(
              "max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap",
              m.role === "user"
                ? "ml-auto bg-brand text-brand-foreground"
                : "bg-black/[0.04] text-ink"
            )}
          >
            {m.content || (streaming && i === messages.length - 1 ? "…" : "")}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {showSuggestions && messages.length < 3 && (
        <div className="flex flex-wrap gap-2 border-t border-black/5 px-4 py-3">
          {siteConfig.suggestedQuestions.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => send(q)}
              className="rounded-full border border-brand/30 px-3 py-1 text-xs text-brand hover:bg-brand/10"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex gap-2 border-t border-black/5 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything…"
          disabled={streaming}
        />
        <Button type="submit" disabled={streaming || !input.trim()} aria-label="Send">
          {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </form>
    </Card>
  );
}
