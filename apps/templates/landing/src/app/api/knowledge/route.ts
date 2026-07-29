import { NextRequest, NextResponse } from "next/server";
import { site } from "@/lib/config";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q")?.trim();
  if (!query) return NextResponse.json({ results: [] });
  if (!site.apiKey) {
    return NextResponse.json({ results: [], error: "Missing NEXT_PUBLIC_AGENT_API_KEY" }, { status: 500 });
  }

  // The published agent already performs RAG against its attached knowledge base.
  // This keeps the starter compatible with the existing public API.
  const response = await fetch(`${site.apiUrl}/public/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: site.apiKey,
      message: `Search the connected knowledge base for: "${query}". Return only concise relevant facts.`
    })
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return NextResponse.json({ results: [], error: data.detail || "Search failed" }, { status: response.status });
  }
  return NextResponse.json({
    query,
    results: [{ document_name: "Connected knowledge", text: data.reply || "", score: 1 }]
  });
}
