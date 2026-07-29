import { useEffect } from "react";

/** Drop-in React helper — loads CDN widget.js */
export function ThtwaatWidget({
  apiKey,
  apiBaseUrl = "http://localhost:8000",
}: {
  apiKey: string;
  apiBaseUrl?: string;
}) {
  useEffect(() => {
    const s = document.createElement("script");
    s.src = `${apiBaseUrl}/widget.js`;
    s.async = true;
    s.dataset.apiKey = apiKey;
    s.dataset.theme = "light";
    s.dataset.position = "bottom-right";
    document.body.appendChild(s);
    return () => {
      window.THTWAAT?.destroy?.();
      s.remove();
    };
  }, [apiKey, apiBaseUrl]);

  return null;
}
