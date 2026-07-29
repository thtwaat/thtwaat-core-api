import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

const schema = z.object({
  type: z.enum(["contact", "newsletter", "demo", "quote"]),
  name: z.string().max(120).optional(),
  email: z.string().email(),
  company: z.string().max(160).optional(),
  message: z.string().max(4000).optional()
});

export async function POST(request: NextRequest) {
  try {
    const lead = schema.parse(await request.json());
    const event = {
      event: `lead.${lead.type}`,
      data: lead,
      source: "ai-landing-starter",
      received_at: new Date().toISOString()
    };
    const webhook = process.env.LEADS_WEBHOOK_URL;

    if (webhook) {
      const response = await fetch(webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event)
      });
      if (!response.ok) throw new Error(`Lead destination returned ${response.status}`);
    } else {
      // Production-safe fallback: hosting logs retain the structured event.
      // Configure LEADS_WEBHOOK_URL to an existing THTWAAT webhook/CRM automation.
      console.info(JSON.stringify(event));
    }
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Invalid lead" },
      { status: 400 }
    );
  }
}
