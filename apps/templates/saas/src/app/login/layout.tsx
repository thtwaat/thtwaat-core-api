import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = noIndexMetadata({
  title: "Sign in",
  description: "Sign in to your THTWAAT workspace.",
  path: "/login"
});

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
