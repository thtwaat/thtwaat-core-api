import { useMemo, useState } from "react";
import { THTWAAT } from "@thtwaat/sdk";

export function ChatBox({ apiKey }: { apiKey: string }) {
  const client = useMemo(
    () =>
      new THTWAAT({
        apiKey,
        apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
      }),
    [apiKey]
  );
  const [reply, setReply] = useState("");

  return (
    <div>
      <button
        onClick={async () => {
          const res = await client.chat("Hello from React");
          setReply(res.reply);
        }}
      >
        Ask
      </button>
      <p>{reply}</p>
    </div>
  );
}
