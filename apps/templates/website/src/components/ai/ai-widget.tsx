"use client";

import Script from "next/script";
import { getApiUrl, getAgentApiKey, siteConfig } from "@/lib/config";

/**
 * Floating AI Widget — loads THTWAAT widget.js with almost zero config.
 */
export function AiWidget() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || getApiUrl();
  const apiKey = process.env.NEXT_PUBLIC_AGENT_API_KEY || getAgentApiKey();
  if (!apiKey) return null;

  return (
    <Script
      id="thtwaat-widget"
      src={`${apiUrl.replace(/\/$/, "")}/widget.js`}
      strategy="afterInteractive"
      data-api-key={apiKey}
      data-theme={process.env.NEXT_PUBLIC_WIDGET_THEME || "auto"}
      data-position={process.env.NEXT_PUBLIC_WIDGET_POSITION || "bottom-right"}
      data-agent-name={siteConfig.name}
      data-welcome={`Hi! I'm the ${siteConfig.name} assistant. Ask me anything.`}
      data-prompts={siteConfig.suggestedQuestions.join("|")}
      data-primary-color={siteConfig.brandColor}
    />
  );
}
