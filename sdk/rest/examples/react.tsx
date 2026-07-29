import { useMemo, useState } from "react";
import { RestClient } from "@thtwaat/rest";

export function RestChat({ apiKey }: { apiKey: string }) {
  const api = useMemo(
    () =>
      new RestClient({
        apiKey,
        apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
      }),
    [apiKey]
  );
  const [text, setText] = useState("");

  return (
    <button
      onClick={async () => {
        const res = await api.agents.chat({ message: "Hello from React" });
        setText((res as any).reply);
      }}
    >
      {text || "Ask"}
    </button>
  );
}
