import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  countryCurrency,
  countryFromBrowserLocale,
  filterBillingCountries,
  resolveInitialBillingCountry,
  writeStoredBillingCountry,
  readStoredBillingCountry
} from "./billing-countries";

describe("billing countries", () => {
  const store = new Map<string, string>();

  beforeEach(() => {
    store.clear();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => {
        store.set(k, v);
      },
      removeItem: (k: string) => {
        store.delete(k);
      }
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps India to INR and others to USD", () => {
    expect(countryCurrency("IN")).toBe("INR");
    expect(countryCurrency("US")).toBe("USD");
    expect(countryCurrency("GB")).toBe("USD");
  });

  it("filters countries by name and code", () => {
    expect(filterBillingCountries("ind").some((c) => c.code === "IN")).toBe(true);
    expect(filterBillingCountries("us").some((c) => c.code === "US")).toBe(true);
    expect(filterBillingCountries("zzzz")).toHaveLength(0);
  });

  it("parses browser locale country", () => {
    expect(countryFromBrowserLocale("en-IN")).toBe("IN");
    expect(countryFromBrowserLocale("en-US")).toBe("US");
    expect(countryFromBrowserLocale("hi")).toBeNull();
  });

  it("prefers stored then non-default server then browser then US", () => {
    expect(
      resolveInitialBillingCountry({
        stored: "GB",
        serverCountry: "IN",
        serverSource: "company",
        browserCountry: "US"
      })
    ).toBe("GB");

    expect(
      resolveInitialBillingCountry({
        serverCountry: "IN",
        serverSource: "header",
        browserCountry: "US"
      })
    ).toBe("IN");

    expect(
      resolveInitialBillingCountry({
        serverCountry: "US",
        serverSource: "default",
        browserCountry: "IN"
      })
    ).toBe("IN");

    expect(resolveInitialBillingCountry({ serverSource: "default" })).toBe("US");
  });

  it("persists selection in localStorage", () => {
    writeStoredBillingCountry("in");
    expect(readStoredBillingCountry()).toBe("IN");
  });
});
