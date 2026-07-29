import type { WidgetTheme, WidgetThemeMode } from "./types";

export const DEFAULT_THEME: WidgetTheme = {
  mode: "light",
  primaryColor: "#111827",
  borderRadius: "16px",
  fontFamily:
    'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  avatarUrl: null,
  logoUrl: null,
};

export function resolveMode(mode: WidgetThemeMode): "light" | "dark" {
  if (mode === "auto") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return mode;
}

export function mergeTheme(
  base: WidgetTheme,
  patch?: Partial<WidgetTheme> | WidgetThemeMode
): WidgetTheme {
  if (!patch) return { ...base };
  if (typeof patch === "string") {
    return { ...base, mode: patch };
  }
  return { ...base, ...patch };
}

export function applyThemeVars(
  root: HTMLElement,
  theme: WidgetTheme
): "light" | "dark" {
  const resolved = resolveMode(theme.mode);
  root.dataset.theme = resolved;
  root.style.setProperty("--tht-primary", theme.primaryColor);
  root.style.setProperty("--tht-radius", theme.borderRadius);
  root.style.setProperty("--tht-font", theme.fontFamily);
  return resolved;
}
