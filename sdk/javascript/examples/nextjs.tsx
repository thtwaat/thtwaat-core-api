"use client";

import { ChatBox } from "./react";

export default function Page() {
  return <ChatBox apiKey={process.env.NEXT_PUBLIC_THTWAAT_KEY || ""} />;
}
