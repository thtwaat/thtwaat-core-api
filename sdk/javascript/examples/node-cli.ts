#!/usr/bin/env node
import { THTWAAT } from "@thtwaat/sdk";

async function main() {
  const message = process.argv.slice(2).join(" ") || "Hello";
  const client = new THTWAAT({
    apiKey: process.env.THTWAAT_API_KEY!,
    apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
  });

  process.stdout.write("Assistant: ");
  for await (const ev of client.streamChat(message)) {
    if (ev.type === "token") process.stdout.write(ev.text);
    if (ev.type === "done") process.stdout.write("\n");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
