// Coding AI — types and helpers for the existing app/coding_agent proxy
// (Phase 6C-1/6C-2 on the backend; this is Phase 6C-3's first frontend
// consumer). The proxy forwards to a separate, already-deployed system
// (AI_Project's AgentRuntime) — Core's contract here is deliberately thin:
// no list-tasks endpoint, no SSE/websocket, and `status`/`phase` are plain
// opaque strings (not a closed enum) since AI_Project owns that vocabulary.
// `result`/`error` are untyped dicts passed through Core's envelope
// unsanitized on the inside — see summarizeCodingResult() below.

export type CodingBudgetSpec = {
  max_turns?: number;
  max_tool_calls?: number;
  max_cost_usd?: number;
  max_execution_seconds?: number;
};

export type CodingTaskCreateRequest = {
  goal: string;
  budget?: CodingBudgetSpec;
};

export type CodingTask = {
  task_id: string;
  status: string;
  phase?: string | null;
  termination_code?: string | null;
  created_at: number;
  updated_at: number;
  started_at?: number | null;
  ended_at?: number | null;
  result?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
};

export type CodingTaskCancelResult = {
  task_id: string;
  status: string;
  cancel_requested: boolean;
  message: string;
};

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function codingTaskStatusLabel(status: string): string {
  switch (status.toLowerCase()) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

export function codingTaskStatusTone(status: string): "neutral" | "success" | "warn" | "danger" | "brand" {
  const s = status.toLowerCase();
  if (s === "completed") return "success";
  if (s === "failed" || s === "cancelled") return "danger";
  if (s === "queued" || s === "running") return "warn";
  return "neutral";
}

export function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.has(status.toLowerCase());
}

export function isBusyStatus(status: string): boolean {
  return !isTerminalStatus(status);
}

// Backend status vocabulary is opaque, so an unrecognized non-terminal
// string must not poll forever — cap at ~12 minutes (180 * 4s), matching
// this panel's own poll interval.
export const MAX_TASK_POLL_ATTEMPTS = 180;

export function shouldContinuePolling(status: string, attempt: number): boolean {
  return isBusyStatus(status) && attempt < MAX_TASK_POLL_ATTEMPTS;
}

const SECRET_KEY_PATTERN = /token|secret|password|api[_-]?key|credential|authorization/i;
const MAX_SUMMARY_DEPTH = 3;
const MAX_SUMMARY_CHARS = 4000;
const MAX_STRING_CHARS = 2000;
const MAX_ARRAY_ITEMS = 50;

function sanitizeForDisplay(value: unknown, depth: number): unknown {
  if (depth > MAX_SUMMARY_DEPTH) return "…";
  if (typeof value === "string") {
    return value.length > MAX_STRING_CHARS ? `${value.slice(0, MAX_STRING_CHARS)}…` : value;
  }
  if (Array.isArray(value)) {
    const items = value.slice(0, MAX_ARRAY_ITEMS).map((v) => sanitizeForDisplay(v, depth + 1));
    if (value.length > MAX_ARRAY_ITEMS) items.push(`…(${value.length - MAX_ARRAY_ITEMS} more)`);
    return items;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, v] of Object.entries(value as Record<string, unknown>)) {
      if (SECRET_KEY_PATTERN.test(key)) {
        out[key] = "[redacted]";
        continue;
      }
      out[key] = sanitizeForDisplay(v, depth + 1);
    }
    return out;
  }
  return value;
}

/**
 * Safe, best-effort renderer for the untyped result/error dicts the backend
 * passes through from AI_Project. There is no dedicated diff/files field in
 * the contract, so this opportunistically surfaces common-sounding keys
 * (summary/message/files/diff) as a headline and otherwise falls back to a
 * capped, depth-limited, secret-redacted JSON view. Never throws.
 */
export function summarizeCodingResult(payload: unknown): string {
  try {
    if (payload == null) return "";
    const sanitized = sanitizeForDisplay(payload, 0);

    const lines: string[] = [];
    if (sanitized && typeof sanitized === "object" && !Array.isArray(sanitized)) {
      const obj = sanitized as Record<string, unknown>;
      if (typeof obj.summary === "string" && obj.summary.trim()) lines.push(obj.summary.trim());
      else if (typeof obj.message === "string" && obj.message.trim()) lines.push(obj.message.trim());
      if (obj.files != null) lines.push(`Files: ${JSON.stringify(obj.files)}`);
      if (obj.diff != null && typeof obj.diff === "string") lines.push(`Diff:\n${obj.diff}`);
    }

    const json = JSON.stringify(sanitized, null, 2) ?? String(sanitized);
    if (lines.length === 0) lines.push(json);

    const combined = lines.join("\n\n");
    return combined.length > MAX_SUMMARY_CHARS ? `${combined.slice(0, MAX_SUMMARY_CHARS)}…` : combined;
  } catch {
    return "Unable to display result.";
  }
}

// Single-active-task persistence — there is no list-tasks endpoint, so the
// panel remembers only the most recent task per browser and resumes polling
// it on reload. Project selection is UI-only labeling (never sent to the
// backend), stored here purely for display continuity across a reload.
const ACTIVE_TASK_STORAGE_KEY = "tht_coding_agent_active_task";

export type ActiveCodingTask = {
  taskId: string;
  projectId: string | null;
  createdAt: number;
};

function getLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readActiveTask(): ActiveCodingTask | null {
  const storage = getLocalStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(ACTIVE_TASK_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ActiveCodingTask>;
    if (typeof parsed?.taskId !== "string" || !parsed.taskId) return null;
    return {
      taskId: parsed.taskId,
      projectId: typeof parsed.projectId === "string" ? parsed.projectId : null,
      createdAt: typeof parsed.createdAt === "number" ? parsed.createdAt : Date.now()
    };
  } catch {
    return null;
  }
}

export function writeActiveTask(entry: ActiveCodingTask): void {
  const storage = getLocalStorage();
  if (!storage) return;
  try {
    storage.setItem(ACTIVE_TASK_STORAGE_KEY, JSON.stringify(entry));
  } catch {
    // Ignore quota/serialization errors — worst case, resume-on-reload is skipped.
  }
}

export function clearActiveTask(): void {
  const storage = getLocalStorage();
  if (!storage) return;
  try {
    storage.removeItem(ACTIVE_TASK_STORAGE_KEY);
  } catch {
    // Ignore.
  }
}

export function generateIdempotencyKey(): string {
  return crypto.randomUUID();
}
