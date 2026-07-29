export type LogLevel = "debug" | "info" | "warn" | "error" | "silent";

export class Logger {
  constructor(
    private enabled: boolean,
    private level: LogLevel = "info"
  ) {}

  private ok(level: LogLevel): boolean {
    if (!this.enabled || this.level === "silent") return false;
    const order: LogLevel[] = ["debug", "info", "warn", "error", "silent"];
    return order.indexOf(level) >= order.indexOf(this.level);
  }

  debug(...args: unknown[]): void {
    if (this.ok("debug")) console.debug("[thtwaat]", ...args);
  }
  info(...args: unknown[]): void {
    if (this.ok("info")) console.info("[thtwaat]", ...args);
  }
  warn(...args: unknown[]): void {
    if (this.ok("warn")) console.warn("[thtwaat]", ...args);
  }
  error(...args: unknown[]): void {
    if (this.ok("error")) console.error("[thtwaat]", ...args);
  }
}
