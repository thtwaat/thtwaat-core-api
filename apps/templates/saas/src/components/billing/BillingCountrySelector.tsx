"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  countryCurrency,
  filterBillingCountries,
  findBillingCountry,
  type BillingCountry
} from "@/lib/billing-countries";

type Props = {
  value: string;
  onChange: (code: string) => void;
  disabled?: boolean;
};

export function BillingCountrySelector({ value, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = findBillingCountry(value) || {
    code: value || "US",
    name: value || "United States",
    flag: "🏳️"
  };
  const currency = countryCurrency(value);
  const options = useMemo(() => filterBillingCountries(query), [query]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function pick(country: BillingCountry) {
    onChange(country.code);
    setOpen(false);
    setQuery("");
  }

  return (
    <div
      ref={rootRef}
      className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-white/60 px-3 py-2.5"
    >
      <div className="relative min-w-[220px] flex-1">
        <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
          Country
        </span>
        <button
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-2 rounded-lg border border-line bg-white px-3 py-2 text-left text-sm disabled:opacity-60"
        >
          <span className="flex items-center gap-2 truncate">
            <span aria-hidden>{selected.flag}</span>
            <span>{selected.name}</span>
          </span>
          <span className="text-muted" aria-hidden>
            ▼
          </span>
        </button>
        {open ? (
          <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-line bg-white shadow-lg">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search country…"
              className="w-full border-b border-line px-3 py-2 text-sm outline-none"
              aria-label="Search country"
            />
            <ul role="listbox" className="max-h-56 overflow-y-auto py-1">
              {options.map((c) => (
                <li key={c.code}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={c.code === selected.code}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                      c.code === selected.code ? "bg-slate-50 font-medium" : ""
                    }`}
                    onClick={() => pick(c)}
                  >
                    <span aria-hidden>{c.flag}</span>
                    <span className="flex-1">{c.name}</span>
                    <span className="text-xs text-muted">{c.code}</span>
                  </button>
                </li>
              ))}
              {!options.length ? (
                <li className="px-3 py-2 text-sm text-muted">No countries match</li>
              ) : null}
            </ul>
          </div>
        ) : null}
      </div>
      <div>
        <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
          Currency
        </span>
        <p className="text-sm font-semibold tabular-nums">{currency}</p>
      </div>
    </div>
  );
}
