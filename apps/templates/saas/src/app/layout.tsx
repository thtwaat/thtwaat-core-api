import type { Metadata } from "next";
import { Providers } from "@/lib/providers";
import { site } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: `${site.name} — AI SaaS Starter`,
    template: `%s · ${site.name}`
  },
  description: "Production-ready AI SaaS dashboard connected to the THTWAAT Core API."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
