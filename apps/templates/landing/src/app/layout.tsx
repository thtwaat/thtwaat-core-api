import type { Metadata } from "next";
import { DM_Sans, Fraunces } from "next/font/google";
import Script from "next/script";
import { site } from "@/lib/config";
import "./globals.css";

const sans = DM_Sans({ subsets: ["latin"], variable: "--font-sans" });
const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: `${site.name} — AI conversations that convert`,
  description: site.description,
  openGraph: {
    title: `${site.name} — AI conversations that convert`,
    description: site.description,
    url: site.url,
    siteName: site.name,
    type: "website",
    images: [{ url: "/og.svg", width: 1200, height: 630 }]
  },
  twitter: {
    card: "summary_large_image",
    title: `${site.name} — AI conversations that convert`,
    description: site.description,
    images: ["/og.svg"]
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true }
  }
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: site.name,
      url: site.url,
      description: site.description
    },
    {
      "@type": "SoftwareApplication",
      name: site.name,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      offers: { "@type": "Offer", price: "49", priceCurrency: "USD" }
    }
  ]
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body className="font-[var(--font-sans)]">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {children}
        {site.apiKey && (
          <Script
            src={`${site.apiUrl}/widget.js`}
            strategy="afterInteractive"
            data-api-key={site.apiKey}
            data-theme="light"
            data-position="bottom-right"
            data-agent-name={site.name}
            data-welcome="Hi — what would you like to achieve?"
            data-prompts={site.suggestedQuestions.join("|")}
            data-primary-color="#136f63"
          />
        )}
      </body>
    </html>
  );
}
