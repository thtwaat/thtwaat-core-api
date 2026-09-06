import type { Metadata } from "next";
import Script from "next/script";
import { IBM_Plex_Mono, IBM_Plex_Sans, Fraunces } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { PageViewTracker } from "@/components/analytics/page-view-tracker";
import { site } from "@/lib/config";
import "./globals.css";

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-geist"
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono"
});
const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: `${site.name} — API Docs & SDKs`,
    template: `%s · ${site.name}`
  },
  description: site.description,
  openGraph: {
    title: site.name,
    description: site.description,
    url: site.url,
    siteName: site.name,
    type: "website"
  },
  twitter: {
    card: "summary_large_image",
    title: site.name,
    description: site.description
  },
  robots: { index: true, follow: true }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${sans.variable} ${mono.variable} ${display.variable}`}>
      <body className="min-h-screen bg-canvas font-sans text-ink antialiased">
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
        <ThemeProvider>
          <PageViewTracker />
          <SiteHeader />
          <main className="mx-auto min-h-[70vh] max-w-7xl px-4 py-8 sm:px-6">{children}</main>
          <SiteFooter />
        </ThemeProvider>
      </body>
    </html>
  );
}
