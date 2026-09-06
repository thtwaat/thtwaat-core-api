import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = noIndexMetadata({
  title: "Signing in",
  description: "Completing sign-in.",
  path: "/auth/callback"
});

export default function AuthCallbackLayout({ children }: { children: React.ReactNode }) {
  return children;
}
