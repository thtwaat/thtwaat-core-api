import type { Metadata } from "next";
import Script from "next/script";
import { Providers } from "@/lib/providers";
import { site } from "@/lib/config";
import "./globals.css";

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: "THTWAAT — AI Agent Platform for Chat, Voice & Automation",
    template: `%s · ${site.name}`
  },
  description:
    "Build AI agents with chat, voice calling, and knowledge search — auth, billing, and custom domains included. Create a workspace free, no backend required.",
  alternates: { canonical: site.url },
  openGraph: {
    type: "website",
    url: site.url,
    title: "THTWAAT — Build AI Agents for Chat, Voice & SaaS",
    description:
      "An AI agent platform with chat, voice calling, knowledge search, billing, and custom domains — wired to a production API from day one.",
    siteName: site.name
  },
  twitter: {
    card: "summary_large_image",
    title: "THTWAAT — AI Agents for Chat, Voice & SaaS",
    description:
      "Build and launch AI agents with chat, voice calling, and knowledge search. Auth, billing, and custom domains included."
  },
  robots: { index: true, follow: true, googleBot: { index: true, follow: true } }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {GA_MEASUREMENT_ID ? (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
              strategy="afterInteractive"
            />
            <Script id="ga4-init" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${GA_MEASUREMENT_ID}', {
                  send_page_view: false,
                  allow_google_signals: false,
                  anonymize_ip: true
                });
                window.gtag = gtag;
              `}
            </Script>
          </>
        ) : null}
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
