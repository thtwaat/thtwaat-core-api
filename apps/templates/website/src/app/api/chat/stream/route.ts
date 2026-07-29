import { NextRequest } from "next/server";
import { getAgentApiKey, getApiUrl } from "@/lib/config";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const apiUrl = getApiUrl();
  const apiKey = getAgentApiKey();

  if (!apiKey) {
    return new Response(`event: error\ndata: ${JSON.stringify({ message: "Missing API key" })}\n\n`, {
      headers: { "Content-Type": "text/event-stream" },
      status: 500,
    });
  }

  const upstream = await fetch(`${apiUrl}/public/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey,
      message: body.message,
      session_id: body.session_id,
    }),
  });

  if (!upstream.ok || !upstream.body) {
    // Fallback: non-stream chat then emit as SSE
    const fallback = await fetch(`${apiUrl}/public/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        message: body.message,
        session_id: body.session_id,
      }),
    });
    const data = await fallback.json().catch(() => ({}));
    const reply = data.reply || data.detail || "Stream unavailable";
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        const chunk = Math.max(1, Math.floor(String(reply).length / 40));
        for (let i = 0; i < String(reply).length; i += chunk) {
          const text = String(reply).slice(i, i + chunk);
          controller.enqueue(
            encoder.encode(`event: token\ndata: ${JSON.stringify({ text })}\n\n`)
          );
        }
        controller.enqueue(
          encoder.encode(
            `event: done\ndata: ${JSON.stringify({
              reply,
              conversation_id: data.conversation_id,
            })}\n\n`
          )
        );
        controller.close();
      },
    });
    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
