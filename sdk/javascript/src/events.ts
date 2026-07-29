import type { SdkEventMap, SdkEventName } from "./types";

type Handler<T> = (payload: T) => void;

export class EventBus {
  private listeners = new Map<string, Set<Handler<unknown>>>();

  on<E extends SdkEventName>(event: E, handler: Handler<SdkEventMap[E]>): () => void {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(handler as Handler<unknown>);
    return () => this.off(event, handler);
  }

  off<E extends SdkEventName>(event: E, handler: Handler<SdkEventMap[E]>): void {
    this.listeners.get(event)?.delete(handler as Handler<unknown>);
  }

  emit<E extends SdkEventName>(event: E, payload: SdkEventMap[E]): void {
    const set = this.listeners.get(event);
    if (!set) return;
    for (const handler of set) {
      try {
        handler(payload);
      } catch {
        /* never break emitters */
      }
    }
  }

  removeAll(): void {
    this.listeners.clear();
  }
}
