const PREFIX = "thtwaat_widget_";

export function storageKey(apiKey: string, suffix: string): string {
  const short = apiKey.slice(-12);
  return `${PREFIX}${short}_${suffix}`;
}

export function loadSession(apiKey: string): string | null {
  try {
    return localStorage.getItem(storageKey(apiKey, "session"));
  } catch {
    return null;
  }
}

export function saveSession(apiKey: string, conversationId: string): void {
  try {
    localStorage.setItem(storageKey(apiKey, "session"), conversationId);
  } catch {
    /* ignore quota / private mode */
  }
}

export function loadHistory(apiKey: string): Array<{
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: number;
}> {
  try {
    const raw = localStorage.getItem(storageKey(apiKey, "history"));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(-50) : [];
  } catch {
    return [];
  }
}

export function saveHistory(
  apiKey: string,
  history: Array<{
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    createdAt: number;
  }>
): void {
  try {
    localStorage.setItem(
      storageKey(apiKey, "history"),
      JSON.stringify(history.slice(-50))
    );
  } catch {
    /* ignore */
  }
}

export function clearSession(apiKey: string): void {
  try {
    localStorage.removeItem(storageKey(apiKey, "session"));
    localStorage.removeItem(storageKey(apiKey, "history"));
  } catch {
    /* ignore */
  }
}
