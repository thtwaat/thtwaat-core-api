import { NextRequest, NextResponse } from "next/server";
import { getAgentApiKey, getApiUrl } from "@/lib/config";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const message = String(body.message || "");
    if (!message) {
      return NextResponse.json({ error: "message required" }, { status: 400 });
    }

    const apiUrl = getApiUrl();
    const apiKey = getAgentApiKey();
    if (!apiKey) {
      return NextResponse.json(
        { error: "Set AGENT_API_KEY or NEXT_PUBLIC_AGENT_API_KEY" },
        { status: 500 }
      );
    }

    const res = await fetch(`${apiUrl}/public/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        message,
        session_id: body.session_id,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || "Upstream chat failed", ...data },
        { status: res.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Chat failed" },
      { status: 500 }
    );
  }
}
