import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

const LeadSchema = z.object({
  type: z.enum(["contact", "newsletter", "demo", "quote"]).default("contact"),
  name: z.string().optional(),
  email: z.string().email(),
  company: z.string().optional(),
  budget: z.string().optional(),
  message: z.string().optional(),
});

export async function POST(req: NextRequest) {
  try {
    const json = await req.json();
    const data = LeadSchema.parse(json);

    const webhook = process.env.LEADS_WEBHOOK_URL;
    if (webhook) {
      await fetch(webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, received_at: new Date().toISOString() }),
      });
    } else {
      console.info("[lead]", JSON.stringify(data));
    }

    return NextResponse.json({
      ok: true,
      message:
        data.type === "newsletter"
          ? "You're subscribed."
          : data.type === "demo"
            ? "Demo request received — we'll schedule soon."
            : "Thanks! We'll get back to you shortly.",
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Invalid lead payload" },
      { status: 400 }
    );
  }
}
