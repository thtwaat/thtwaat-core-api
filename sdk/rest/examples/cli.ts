#!/usr/bin/env node
import { RestClient } from "@thtwaat/rest";

const api = new RestClient({
  apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
  apiKey: process.env.THTWAAT_API_KEY!,
});

const msg = process.argv.slice(2).join(" ") || "Hello";

for await (const ev of api.agents.streamChat({ message: msg })) {
  if (ev.event === "token") process.stdout.write(String((ev.data as any).text || ""));
  if (ev.event === "done") process.stdout.write("\n");
}
