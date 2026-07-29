"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";

type LeadType = "contact" | "newsletter" | "demo" | "quote";

export function LeadForm({
  type,
  compact = false
}: {
  type: LeadType;
  compact?: boolean;
}) {
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("sending");
    const body = Object.fromEntries(new FormData(event.currentTarget));
    const response = await fetch("/api/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, ...body })
    });
    setState(response.ok ? "sent" : "error");
    if (response.ok) event.currentTarget.reset();
  }

  if (state === "sent") {
    return (
      <div className="flex items-center gap-3 rounded-2xl bg-mint p-5 text-brand">
        <CheckCircle2 />
        <p className="font-semibold">You’re in. We’ll follow up shortly.</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className={compact ? "flex gap-2" : "grid gap-3"}>
      {!compact && (
        <>
          <Input name="name" required placeholder="Your name" />
          <Input name="company" placeholder="Company" />
        </>
      )}
      <Input
        name="email"
        required
        type="email"
        placeholder="Work email"
        className={compact ? "min-w-0 flex-1 rounded-full" : undefined}
      />
      {!compact && type !== "newsletter" && (
        <Textarea
          name="message"
          placeholder={
            type === "quote"
              ? "What would you like us to build?"
              : "What would you like to achieve?"
          }
        />
      )}
      <Button
        type="submit"
        disabled={state === "sending"}
        className={compact ? "shrink-0" : "w-full"}
      >
        {state === "sending"
          ? "Sending…"
          : type === "newsletter"
            ? "Subscribe"
            : type === "demo"
              ? "Book my demo"
              : type === "quote"
                ? "Request quote"
                : "Send message"}
        {state !== "sending" && <ArrowRight size={16} />}
      </Button>
      {state === "error" && (
        <p className="text-sm text-red-600">Could not submit. Please try again.</p>
      )}
    </form>
  );
}
