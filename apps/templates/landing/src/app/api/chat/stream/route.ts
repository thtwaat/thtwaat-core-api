import { NextRequest } from "next/server";
import { site } from "@/lib/config";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const body = await request.json();
  if (!site.apiKey) {
    return new Response(
      `event: error\ndata: ${JSON.stringify({ message: "Set NEXT_PUBLIC_AGENT_API_KEY" })}\n\n`,
      { status: 500, headers: { "Content-Type": "text/event-stream" } }
    );
  }

  const payload = {
    api_key: site.apiKey,
    message: String(body.message || ""),
    session_id: body.session_id
  };
  const upstream = await fetch(`${site.apiUrl}/public/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: request.signal
  });

  if (upstream.ok && upstream.body) {
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive"
      }
    });
  }

  const fallback = await fetch(`${site.apiUrl}/public/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await fallback.json().catch(() => ({}));
  const encoder = new TextEncoder();
  const reply = String(data.reply || data.detail || "The assistant is unavailable.");
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode(`event: token\ndata: ${JSON.stringify({ text: reply })}\n\n`)
      );
      controller.enqueue(
        encoder.encode(
          `event: done\ndata: ${JSON.stringify({
            reply,
            conversation_id: data.conversation_id
          })}\n\n`
        )
      );
      controller.close();
    }
  });
  return new Response(stream, {
    status: fallback.ok ? 200 : fallback.status,
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" }
  });
}
