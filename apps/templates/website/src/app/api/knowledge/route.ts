import { NextRequest, NextResponse } from "next/server";
import { getAgentApiKey, getApiUrl } from "@/lib/config";

/**
 * Knowledge search proxy.
 * Uses platform knowledge search when authenticated JWT is available;
 * otherwise returns a helpful empty result so the UI stays resilient.
 */
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") || "";
  const topK = Number(req.nextUrl.searchParams.get("top_k") || 5);
  if (!q) return NextResponse.json({ query: q, results: [] });

  const apiUrl = getApiUrl();
  const apiKey = getAgentApiKey();

  // Prefer asking the agent (RAG-backed public chat) as a knowledge answer snippet
  // when dedicated public knowledge search is not exposed without JWT.
  try {
    if (apiKey) {
      const res = await fetch(`${apiUrl}/public/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          message: `Search knowledge for: ${q}. Reply with the most relevant facts only.`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        return NextResponse.json({
          query: q,
          results: [
            {
              document_name: "Agent knowledge",
              text: data.reply,
              score: 1,
            },
          ].slice(0, topK),
        });
      }
    }
  } catch {
    /* fall through */
  }

  return NextResponse.json({
    query: q,
    results: [],
    hint: "Connect a published agent with a knowledge base for semantic search.",
  });
}
