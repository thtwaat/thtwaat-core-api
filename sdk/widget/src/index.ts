import { Widget } from "./Widget";
import type { THTWAATApi, WidgetRuntimeOptions } from "./types";

export type {
  WidgetConfig,
  WidgetTheme,
  WidgetThemeMode,
  WidgetPosition,
  WidgetEvents,
  THTWAATApi,
  WidgetRuntimeOptions,
  ChatMessage,
  PublicChatResponse,
} from "./types";

export { Widget };
export const version = "1.0.0";

function findCurrentScript(): HTMLScriptElement | null {
  const current = document.currentScript;
  if (current && current instanceof HTMLScriptElement) return current;
  const scripts = Array.from(document.getElementsByTagName("script"));
  return (
    scripts.reverse().find((s) => (s.getAttribute("src") || "").includes("widget")) ||
    null
  );
}

export function init(options: WidgetRuntimeOptions): THTWAATApi {
  const instance = new Widget(options);
  const api: THTWAATApi & { version: string } = {
    open: instance.open,
    close: instance.close,
    toggle: instance.toggle,
    sendMessage: instance.sendMessage,
    setTheme: instance.setTheme,
    identifyUser: instance.identifyUser,
    destroy: instance.destroy,
    isOpen: instance.isOpen,
    version,
  };
  window.THTWAAT = Object.assign(api, { init, version });
  return api;
}

function autoBoot(): void {
  const script = findCurrentScript();
  if (!script) return;
  const apiKey = script.getAttribute("data-api-key");
  if (!apiKey) return;
  const instance = Widget.fromScript(script);
  window.THTWAAT = Object.assign(instance, { init, version });
}

if (typeof window !== "undefined") {
  window.THTWAAT = {
    ...(window.THTWAAT || ({} as THTWAATApi)),
    init,
    version,
  } as THTWAATApi & { init?: typeof init; version?: string };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoBoot, { once: true });
  } else {
    autoBoot();
  }
}
