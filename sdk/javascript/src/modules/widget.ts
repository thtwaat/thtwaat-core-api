/**
 * Browser widget bridge — uses window.THTWAAT from @thtwaat/widget /widget.js
 */

export interface WidgetBridgeApi {
  open: () => void;
  close: () => void;
  toggle: () => void;
  sendMessage?: (text: string) => Promise<void>;
  setTheme?: (theme: unknown) => void;
  destroy?: () => void;
  isOpen?: () => boolean;
}

function getGlobalWidget(): WidgetBridgeApi | undefined {
  if (typeof window === "undefined") return undefined;
  return (window as any).THTWAAT as WidgetBridgeApi | undefined;
}

export class WidgetModule {
  private ensure(): WidgetBridgeApi {
    const api = getGlobalWidget();
    if (!api) {
      throw new Error(
        "Widget not loaded. Include /widget.js or call THTWAAT.init() from @thtwaat/widget first."
      );
    }
    return api;
  }

  open(): void {
    this.ensure().open();
  }

  close(): void {
    this.ensure().close();
  }

  toggle(): void {
    this.ensure().toggle();
  }

  sendMessage(text: string): Promise<void> {
    const api = this.ensure();
    if (!api.sendMessage) return Promise.reject(new Error("sendMessage unavailable"));
    return api.sendMessage(text);
  }

  setTheme(theme: unknown): void {
    this.ensure().setTheme?.(theme);
  }

  destroy(): void {
    this.ensure().destroy?.();
  }

  isOpen(): boolean {
    return Boolean(this.ensure().isOpen?.());
  }
}
