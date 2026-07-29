"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { siteConfig } from "@/lib/config";

const STORAGE_KEY = "thtwaat_site_theme";

type ThemeState = {
  brandColor: string;
  logoText: string;
  siteName: string;
};

export function AdminThemePanel() {
  const [theme, setTheme] = useState<ThemeState>({
    brandColor: siteConfig.brandColor,
    logoText: siteConfig.logoText,
    siteName: siteConfig.name,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setTheme({ ...theme, ...JSON.parse(raw) });
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--brand", theme.brandColor);
  }, [theme.brandColor]);

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(theme));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="space-y-4">
        <h2 className="font-display text-xl">Brand & theme</h2>
        <label className="block text-sm">
          Logo text
          <Input
            className="mt-1"
            value={theme.logoText}
            onChange={(e) => setTheme((t) => ({ ...t, logoText: e.target.value }))}
          />
        </label>
        <label className="block text-sm">
          Site name
          <Input
            className="mt-1"
            value={theme.siteName}
            onChange={(e) => setTheme((t) => ({ ...t, siteName: e.target.value }))}
          />
        </label>
        <label className="block text-sm">
          Brand color
          <div className="mt-1 flex gap-2">
            <Input
              type="color"
              className="h-11 w-16 p-1"
              value={theme.brandColor}
              onChange={(e) => setTheme((t) => ({ ...t, brandColor: e.target.value }))}
            />
            <Input
              value={theme.brandColor}
              onChange={(e) => setTheme((t) => ({ ...t, brandColor: e.target.value }))}
            />
          </div>
        </label>
        <Button onClick={save}>{saved ? "Saved" : "Save theme"}</Button>
      </Card>

      <Card className="space-y-4">
        <h2 className="font-display text-xl">Publish & connect</h2>
        <ol className="list-decimal space-y-2 pl-5 text-sm text-ink-muted">
          <li>Publish your agent in THTWAAT Platform and copy the `tht_live_…` key.</li>
          <li>Set `NEXT_PUBLIC_API_URL` + `NEXT_PUBLIC_AGENT_API_KEY` in `.env.local`.</li>
          <li>Deploy to Vercel / Netlify / Docker with one click.</li>
        </ol>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => window.open(process.env.NEXT_PUBLIC_API_URL || "https://api.thtwaat.com/docs", "_blank")}
          >
            One-click Connect (API docs)
          </Button>
          <Button
            variant="outline"
            onClick={() => window.open("https://vercel.com/new", "_blank")}
          >
            One-click Deploy
          </Button>
          <Button onClick={() => (window.location.href = "/chat")}>Test Publish (Chat)</Button>
        </div>
        <p className="text-xs text-ink-muted">
          Navigation & footer links are configured in `src/lib/config.ts`.
        </p>
      </Card>
    </div>
  );
}
