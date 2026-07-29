import { DocsSidebar } from "@/components/site-chrome";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-8">
      <DocsSidebar />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
