import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = noIndexMetadata({
  title: "Forgot password",
  description: "Request a password reset link for your THTWAAT account.",
  path: "/forgot-password"
});

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
