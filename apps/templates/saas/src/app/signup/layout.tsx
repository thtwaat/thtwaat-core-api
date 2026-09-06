import type { Metadata } from "next";
import { noIndexMetadata } from "@/lib/seo";

export const metadata: Metadata = noIndexMetadata({
  title: "Create workspace",
  description: "Create your THTWAAT company workspace and owner account.",
  path: "/signup"
});

export default function SignupLayout({ children }: { children: React.ReactNode }) {
  return children;
}
