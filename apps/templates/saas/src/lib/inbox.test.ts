import { describe, expect, it } from "vitest";
import { buildInboxQuery, channelLabel, statusLabel, statusTone } from "./inbox";

describe("inbox helpers", () => {
  it("labels channels and statuses", () => {
    expect(channelLabel("widget")).toBe("Website widget");
    expect(channelLabel("dashboard")).toBe("Agent / dashboard");
    expect(statusLabel("pending_human")).toBe("Pending handoff");
    expect(statusTone("pending_human")).toBe("warn");
    expect(statusTone("human")).toBe("success");
  });

  it("builds list query strings without social channels", () => {
    expect(buildInboxQuery({ q: " billing ", channel: "widget", status: "open", unread_only: true })).toBe(
      "?q=billing&channel=widget&status=open&unread_only=true"
    );
    expect(buildInboxQuery({ channel: "all", status: "all" })).toBe("");
  });
});
