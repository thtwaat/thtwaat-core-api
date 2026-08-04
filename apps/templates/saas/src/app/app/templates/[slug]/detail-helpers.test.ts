import { describe, expect, it } from "vitest";
import { priceLabel, renderSimpleMarkdown, youtubeEmbedUrl } from "./detail-helpers";

describe("template detail helpers", () => {
  it("formats pricing badges", () => {
    expect(priceLabel(0, "free")).toBe("Free");
    expect(priceLabel(29, "pro", "Pro")).toBe("Pro");
    expect(priceLabel("12", "starter")).toBe("$12");
  });

  it("builds youtube embeds", () => {
    expect(youtubeEmbedUrl("https://www.youtube.com/watch?v=abc123")).toBe(
      "https://www.youtube.com/embed/abc123"
    );
    expect(youtubeEmbedUrl("https://youtu.be/xyz789")).toBe("https://www.youtube.com/embed/xyz789");
    expect(youtubeEmbedUrl(null)).toBeNull();
  });

  it("renders simple markdown", () => {
    const html = renderSimpleMarkdown("## Hello\n\n- one\n- two\n\n**bold**");
    expect(html).toContain("<h3");
    expect(html).toContain("<ul");
    expect(html).toContain("<strong>bold</strong>");
  });
});
