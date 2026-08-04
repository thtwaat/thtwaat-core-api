import { describe, expect, it } from "vitest";
import { formatApiErrorMessage } from "./api";

describe("formatApiErrorMessage", () => {
  it("surfaces platform { error, code } envelope used by OTP/onboarding", () => {
    expect(formatApiErrorMessage({ error: "Invalid OTP", code: 400 }, 400)).toBe("Invalid OTP");
    expect(
      formatApiErrorMessage(
        { error: "Please wait 60 seconds before requesting a new OTP.", code: 429 },
        429
      )
    ).toBe("Please wait 60 seconds before requesting a new OTP.");
    expect(
      formatApiErrorMessage({ error: "Too many OTP requests. Please try again later.", code: 429 }, 429)
    ).toBe("Too many OTP requests. Please try again later.");
    expect(formatApiErrorMessage({ error: "OTP has expired", code: 400 }, 400)).toBe(
      "OTP has expired"
    );
  });

  it("still supports FastAPI { detail } and plain strings", () => {
    expect(formatApiErrorMessage({ detail: "Email is already verified" }, 400)).toBe(
      "Email is already verified"
    );
    expect(formatApiErrorMessage("boom", 500)).toBe("boom");
  });

  it("falls back only when no usable message exists", () => {
    expect(formatApiErrorMessage({}, 400)).toBe("Request failed (400)");
    expect(formatApiErrorMessage(null, 429)).toBe("Request failed (429)");
  });
});
