import type { LucideIcon } from "lucide-react";
import { Bot, BookOpen, CreditCard, Globe2, MessageSquare, Phone, ShieldCheck, Store, Webhook } from "lucide-react";

/**
 * Single source of truth for the real, shipped capabilities of the product —
 * shared by the homepage and /platform so the two pages never describe a
 * capability differently.
 */
export type Capability = {
  icon: LucideIcon;
  title: string;
  description: string;
};

export const capabilities: Capability[] = [
  {
    icon: Bot,
    title: "AI Agents",
    description: "Configure model, tools, and behavior per agent, then publish or clone in a click."
  },
  {
    icon: MessageSquare,
    title: "AI Chat",
    description: "An embeddable chat widget with a shared inbox for every conversation your agents have."
  },
  {
    icon: Phone,
    title: "Voice / Calling",
    description: "Give an agent a phone number, a greeting, and a human handoff line for real calls."
  },
  {
    icon: BookOpen,
    title: "Knowledge",
    description: "Upload documents into knowledge bases and attach them to any agent for grounded answers."
  },
  {
    icon: Webhook,
    title: "Integrations",
    description: "API keys and webhooks push agent, billing, and domain events into your own systems."
  },
  {
    icon: Globe2,
    title: "Deployment / Custom Domains",
    description: "Connect a custom domain and provision SSL without leaving the dashboard."
  },
  {
    icon: Store,
    title: "Marketplace / Templates",
    description: "Install a prebuilt template or describe your product and have it provisioned for you."
  }
];

export const steps = [
  {
    title: "Create your workspace",
    description: "Sign up and get a company workspace provisioned instantly — no backend to stand up."
  },
  {
    title: "Build or generate an agent",
    description: "Configure an agent by hand, or describe your product and let the generator provision it."
  },
  {
    title: "Connect knowledge & channels",
    description: "Attach a knowledge base, then turn on chat, voice calling, or both for that agent."
  },
  {
    title: "Publish",
    description: "Embed the widget, connect a custom domain with SSL, and go live."
  }
];

export type ValueItem = { icon: LucideIcon; text: string };

export const values: ValueItem[] = [
  { icon: ShieldCheck, text: "JWT + OTP authentication out of the box" },
  { icon: CreditCard, text: "Usage tracking and billing, with Stripe and Razorpay checkout" },
  { icon: Globe2, text: "Custom domains with automatic SSL provisioning" },
  { icon: Webhook, text: "Webhooks and API keys for connecting your own systems" }
];
