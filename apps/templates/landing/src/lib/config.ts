export const site = {
  name: process.env.NEXT_PUBLIC_SITE_NAME || "Lumina AI",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3200",
  description:
    "Turn every website visit into a qualified conversation with an AI assistant trained on your business.",
  apiUrl: (process.env.NEXT_PUBLIC_API_URL || "https://api.thtwaat.com").replace(/\/$/, ""),
  apiKey: process.env.NEXT_PUBLIC_AGENT_API_KEY || "",
  suggestedQuestions: [
    "How can this help my team?",
    "Which plan is right for me?",
    "Can I connect my knowledge base?",
    "I'd like to book a demo"
  ]
};
