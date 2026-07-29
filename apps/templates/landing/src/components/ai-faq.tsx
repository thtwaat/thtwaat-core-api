"use client";

import { MessageCircleQuestion } from "lucide-react";

const questions = [
  ["Will it answer from our own content?", "Yes. Attach your THTWAAT knowledge base and the assistant uses it automatically."],
  ["Does chat stream in real time?", "Yes. The inline assistant proxies the existing SSE streaming endpoint with a non-stream fallback."],
  ["Can we use our own domain?", "Yes. Publish the landing page anywhere, then connect and verify your domain in THTWAAT."],
  ["Are leads sent to our systems?", "Set LEADS_WEBHOOK_URL to forward contact, newsletter, demo, and quote events to your automation endpoint."]
];

export function AiFaq() {
  function askAi(question: string) {
    const client = (window as typeof window & {
      THTWAAT?: { open?: () => void; sendMessage?: (text: string) => void };
    }).THTWAAT;
    client?.open?.();
    client?.sendMessage?.(question);
  }

  return (
    <div className="grid gap-4">
      {questions.map(([question, answer]) => (
        <details key={question} className="group rounded-2xl border border-ink/10 bg-white/70 p-5">
          <summary className="cursor-pointer list-none font-semibold">
            <span className="flex items-center justify-between">
              {question}
              <span className="text-brand transition group-open:rotate-45">+</span>
            </span>
          </summary>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">{answer}</p>
          <button
            onClick={() => askAi(question)}
            className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-brand"
          >
            <MessageCircleQuestion size={14} /> Ask the AI for more detail
          </button>
        </details>
      ))}
    </div>
  );
}
