"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

type LeadType = "contact" | "newsletter" | "demo" | "quote";

const titles: Record<LeadType, string> = {
  contact: "Contact us",
  newsletter: "Subscribe to updates",
  demo: "Book a demo",
  quote: "Request a quote",
};

export function LeadForm({ type = "contact" }: { type?: LeadType }) {
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("loading");
    const fd = new FormData(e.currentTarget);
    const payload = Object.fromEntries(fd.entries());
    try {
      const res = await fetch("/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, ...payload }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed");
      setStatus("ok");
      setMessage(data.message || "Thanks — we'll be in touch.");
      e.currentTarget.reset();
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <Card>
      <h3 className="mb-1 font-display text-xl">{titles[type]}</h3>
      <p className="mb-6 text-sm text-ink-muted">We typically reply within one business day.</p>
      <form onSubmit={onSubmit} className="space-y-3">
        {type !== "newsletter" && (
          <Input name="name" placeholder="Full name" required={type !== "newsletter"} />
        )}
        <Input name="email" type="email" placeholder="Work email" required />
        {type === "demo" && <Input name="company" placeholder="Company" />}
        {type === "quote" && <Input name="budget" placeholder="Approx. budget (optional)" />}
        {(type === "contact" || type === "quote" || type === "demo") && (
          <Textarea name="message" placeholder="How can we help?" required={type === "contact"} />
        )}
        <Button type="submit" className="w-full" disabled={status === "loading"}>
          {status === "loading" ? "Sending…" : "Submit"}
        </Button>
        {message && (
          <p className={`text-sm ${status === "error" ? "text-red-600" : "text-brand"}`}>{message}</p>
        )}
      </form>
    </Card>
  );
}
