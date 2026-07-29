"use client";

import Script from "next/script";

export default function NextChatWidget({
  apiKey,
}: {
  apiKey: string;
}) {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return (
    <Script
      src={`${base}/widget.js`}
      data-api-key={apiKey}
      data-theme="auto"
      data-position="bottom-right"
      strategy="afterInteractive"
    />
  );
}
