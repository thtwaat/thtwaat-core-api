import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearActiveTask,
  codingTaskStatusLabel,
  codingTaskStatusTone,
  isBusyStatus,
  isTerminalStatus,
  MAX_TASK_POLL_ATTEMPTS,
  readActiveTask,
  shouldContinuePolling,
  summarizeCodingResult,
  writeActiveTask
} from "./coding-agent";

describe("codingTaskStatusLabel / codingTaskStatusTone", () => {
  it("maps known statuses to expected labels and tones", () => {
    expect(codingTaskStatusLabel("queued")).toBe("Queued");
    expect(codingTaskStatusLabel("running")).toBe("Running");
    expect(codingTaskStatusLabel("completed")).toBe("Completed");
    expect(codingTaskStatusLabel("failed")).toBe("Failed");
    expect(codingTaskStatusLabel("cancelled")).toBe("Cancelled");

    expect(codingTaskStatusTone("completed")).toBe("success");
    expect(codingTaskStatusTone("failed")).toBe("danger");
    expect(codingTaskStatusTone("cancelled")).toBe("danger");
    expect(codingTaskStatusTone("queued")).toBe("warn");
    expect(codingTaskStatusTone("running")).toBe("warn");
  });

  it("never throws on an unrecognized status and returns a readable fallback", () => {
    expect(() => codingTaskStatusLabel("waiting_on_reviewer")).not.toThrow();
    expect(codingTaskStatusLabel("waiting_on_reviewer")).toBe("Waiting On Reviewer");
    expect(codingTaskStatusTone("waiting_on_reviewer")).toBe("neutral");

    expect(() => codingTaskStatusLabel("")).not.toThrow();
    expect(codingTaskStatusTone("")).toBe("neutral");
  });

  it("is case-insensitive", () => {
    expect(codingTaskStatusTone("Completed")).toBe("success");
    expect(codingTaskStatusLabel("RUNNING")).toBe("Running");
  });
});

describe("isTerminalStatus / isBusyStatus", () => {
  it("are complementary for known values", () => {
    for (const s of ["queued", "running", "completed", "failed", "cancelled", "unknown_status"]) {
      expect(isTerminalStatus(s)).toBe(!isBusyStatus(s));
    }
  });

  it("treats completed/failed/cancelled as terminal, case-insensitively", () => {
    expect(isTerminalStatus("completed")).toBe(true);
    expect(isTerminalStatus("Failed")).toBe(true);
    expect(isTerminalStatus("CANCELLED")).toBe(true);
    expect(isTerminalStatus("queued")).toBe(false);
    expect(isTerminalStatus("running")).toBe(false);
  });
});

describe("shouldContinuePolling", () => {
  it("continues while busy and under the attempt ceiling", () => {
    expect(shouldContinuePolling("running", 0)).toBe(true);
    expect(shouldContinuePolling("queued", MAX_TASK_POLL_ATTEMPTS - 1)).toBe(true);
  });

  it("stops once terminal, regardless of attempt count", () => {
    expect(shouldContinuePolling("completed", 0)).toBe(false);
    expect(shouldContinuePolling("failed", 0)).toBe(false);
  });

  it("stops once the attempt ceiling is reached even for an unrecognized busy-looking status", () => {
    expect(shouldContinuePolling("some_unknown_phase", MAX_TASK_POLL_ATTEMPTS)).toBe(false);
    expect(shouldContinuePolling("some_unknown_phase", MAX_TASK_POLL_ATTEMPTS + 1)).toBe(false);
  });
});

describe("summarizeCodingResult", () => {
  it("renders a plain object legibly", () => {
    const out = summarizeCodingResult({ summary: "Added dark mode toggle" });
    expect(out).toContain("Added dark mode toggle");
  });

  it("falls back to generic JSON when no known headline keys are present", () => {
    const out = summarizeCodingResult({ foo: "bar", nested: { baz: 1 } });
    expect(out).toContain("foo");
    expect(out).toContain("bar");
  });

  it("never crashes on a circular reference — depth-capping breaks the cycle", () => {
    const circular: Record<string, unknown> = { a: 1 };
    circular.self = circular;
    expect(() => summarizeCodingResult(circular)).not.toThrow();
    expect(typeof summarizeCodingResult(circular)).toBe("string");
  });

  it("falls back to a safe message if sanitization itself throws", () => {
    const hostile = {
      get poison(): never {
        throw new Error("boom");
      }
    };
    expect(() => summarizeCodingResult(hostile)).not.toThrow();
    expect(summarizeCodingResult(hostile)).toBe("Unable to display result.");
  });

  it("caps very long output", () => {
    const huge = { message: "x".repeat(1_000_000) };
    const out = summarizeCodingResult(huge);
    expect(out.length).toBeLessThan(10_000);
  });

  it("never echoes secret-shaped values, even nested", () => {
    const payload = {
      message: "ok",
      api_key: "sk-should-never-appear",
      nested: { access_token: "leak-me" }
    };
    const out = summarizeCodingResult(payload);
    expect(out).not.toMatch(/sk-should-never-appear/);
    expect(out).not.toMatch(/leak-me/);
  });

  it("handles null/undefined without throwing", () => {
    expect(summarizeCodingResult(null)).toBe("");
    expect(summarizeCodingResult(undefined)).toBe("");
  });
});

describe("active task localStorage persistence", () => {
  const mockStorage = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: (k: string) => (k in store ? store[k] : null),
      setItem: (k: string, v: string) => {
        store[k] = v;
      },
      removeItem: (k: string) => {
        delete store[k];
      },
      clear: () => {
        store = {};
      }
    } as Storage;
  })();

  beforeEach(() => {
    vi.stubGlobal("localStorage", mockStorage);
    vi.stubGlobal("window", { localStorage: mockStorage });
    mockStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("round-trips an active task", () => {
    expect(readActiveTask()).toBeNull();
    writeActiveTask({ taskId: "task-1", projectId: "proj-1", createdAt: 123 });
    expect(readActiveTask()).toEqual({ taskId: "task-1", projectId: "proj-1", createdAt: 123 });
    clearActiveTask();
    expect(readActiveTask()).toBeNull();
  });

  it("treats corrupt JSON as no active task rather than throwing", () => {
    mockStorage.setItem("tht_coding_agent_active_task", "{not valid json");
    expect(() => readActiveTask()).not.toThrow();
    expect(readActiveTask()).toBeNull();
  });
});
