import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = noIndexMetadata({
  title: "Reset password",
  description: "Choose a new password for your THTWAAT account.",
  path: "/reset-password"
});

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
