import { getAgentApiKey, getApiUrl } from "./config";

export type ChatMessage = { role: "user" | "assistant" | "system"; content: string };

export type ChatResult = {
  reply: string;
  conversation_id?: string;
  usage?: Record<string, unknown>;
};

/** Server-side or client-side THTWAAT public chat client */
export async function chatOnce(
  message: string,
  opts?: { sessionId?: string; apiKey?: string; apiUrl?: string }
): Promise<ChatResult> {
  const apiUrl = (opts?.apiUrl || getApiUrl()).replace(/\/$/, "");
  const apiKey = opts?.apiKey || getAgentApiKey();
  if (!apiKey) {
    throw new Error("Missing AGENT_API_KEY / NEXT_PUBLIC_AGENT_API_KEY");
  }

  const res = await fetch(`${apiUrl}/public/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey,
      message,
      session_id: opts?.sessionId,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Chat failed (${res.status})`);
  }
  const data = await res.json();
  return {
    reply: data.reply ?? data.content ?? "",
    conversation_id: data.conversation_id,
    usage: data.usage,
  };
}

/** SSE streaming via public chat/stream endpoint */
export async function* chatStream(
  message: string,
  opts?: { sessionId?: string; signal?: AbortSignal }
): AsyncGenerator<{ type: "token" | "done" | "error"; text?: string; payload?: unknown }> {
  const apiUrl = getApiUrl();
  const apiKey = getAgentApiKey();
  if (!apiKey) {
    yield { type: "error", text: "Missing API key" };
    return;
  }

  const res = await fetch(`${apiUrl}/public/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey,
      message,
      session_id: opts?.sessionId,
    }),
    signal: opts?.signal,
  });

  if (!res.ok || !res.body) {
    yield { type: "error", text: `Stream failed (${res.status})` };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        const parsed = JSON.parse(data);
        if (event === "token") yield { type: "token", text: parsed.text || "" };
        else if (event === "done") yield { type: "done", payload: parsed };
        else if (event === "error") yield { type: "error", text: parsed.message || "error" };
      } catch {
        yield { type: "token", text: data };
      }
    }
  }
}

export async function knowledgeSearch(query: string, topK = 5) {
  const apiUrl = getApiUrl();
  const apiKey = getAgentApiKey();
  // Proxy through our API route to keep keys server-side when possible
  const res = await fetch(`/api/knowledge?q=${encodeURIComponent(query)}&top_k=${topK}`, {
    headers: apiKey ? { "X-API-Key": apiKey } : {},
  });
  if (!res.ok) return { results: [], query };
  return res.json();
}
