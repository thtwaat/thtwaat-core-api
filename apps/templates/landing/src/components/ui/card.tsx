import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({
  className,
  children
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-[2rem] border border-ink/10 bg-white/75 p-6 shadow-soft backdrop-blur",
        className
      )}
    >
      {children}
    </div>
  );
}

export function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-mint px-3 py-1 text-xs font-semibold text-brand",
        className
      )}
    >
      {children}
    </span>
  );
}
