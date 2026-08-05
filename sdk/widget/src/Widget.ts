import { WidgetApiClient } from "./api";
import {
  clearSession,
  loadHistory,
  loadSession,
  saveHistory,
  saveSession,
} from "./storage";
import {
  applyThemeVars,
  DEFAULT_THEME,
  mergeTheme,
} from "./theme";
import type {
  ChatMessage,
  THTWAATApi,
  WidgetPosition,
  WidgetRuntimeOptions,
  WidgetTheme,
  WidgetThemeMode,
} from "./types";
import styles from "./styles.css?inline";
import { widgetStrings, resolveWidgetLocale } from "./i18n";

function uid(prefix = "m"): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function detectBaseUrl(script?: HTMLScriptElement | null): string {
  if (script?.src) {
    try {
      const u = new URL(script.src);
      return `${u.origin}`;
    } catch {
      /* fall through */
    }
  }
  return "http://localhost:8000";
}

export class Widget implements THTWAATApi {
  private options: WidgetRuntimeOptions;
  private theme: WidgetTheme;
  private client: WidgetApiClient;
  private root!: HTMLElement;
  private shadow!: ShadowRoot;
  private panel!: HTMLElement;
  private messagesEl!: HTMLElement;
  private inputEl!: HTMLTextAreaElement;
  private sendBtn!: HTMLButtonElement;
  private launcher!: HTMLButtonElement;
  private badgeEl!: HTMLSpanElement;
  private focusables: HTMLElement[] = [];
  private openState = false;
  private busy = false;
  private unread = 0;
  private conversationId: string | null = null;
  private messages: ChatMessage[] = [];
  private userMeta: Record<string, unknown> = {};
  private destroyed = false;
  private mediaQuery?: MediaQueryList;
  private onMediaChange?: () => void;
  private pollTimer?: ReturnType<typeof setInterval>;
  private lastMessageId: string | null = null;
  private strings = widgetStrings();
  private leadCaptured = false;

  constructor(options: WidgetRuntimeOptions) {
    if (!options.apiKey) {
      throw new Error("THTWAAT Widget: apiKey is required");
    }
    this.options = {
      position: "bottom-right",
      agentName: "AI Assistant",
      welcomeMessage: "Hi! How can I help you today?",
      suggestedPrompts: ["Pricing?", "Book appointment", "Contact support"],
      zIndex: 2147483000,
      openOnLoad: false,
      ...options,
      apiBaseUrl: options.apiBaseUrl || "http://localhost:8000",
    };
    this.theme = mergeTheme(DEFAULT_THEME, options.theme);
    this.client = new WidgetApiClient(this.options.apiBaseUrl, this.options.apiKey);
    this.userMeta = { ...(options.user || {}) };
    const locale = resolveWidgetLocale(options.locale || (this.userMeta.locale as string));
    this.strings = widgetStrings(locale);
    this.userMeta.locale = locale;
    this.conversationId = loadSession(this.options.apiKey);
    this.messages = loadHistory(this.options.apiKey);
    this.leadCaptured = Boolean(
      this.userMeta.email || this.userMeta.name || (this.userMeta.lead as unknown)
    );
    this.mount();
    if (this.options.openOnLoad) this.open();
    this.options.onReady?.(this);
    this.startPolling();
  }

  static fromScript(script: HTMLScriptElement): Widget {
    const apiKey = script.getAttribute("data-api-key") || "";
    const themeMode = (script.getAttribute("data-theme") || "light") as WidgetThemeMode;
    const position = (script.getAttribute("data-position") ||
      "bottom-right") as WidgetPosition;
    const primary =
      script.getAttribute("data-primary-color") ||
      script.getAttribute("data-color") ||
      undefined;
    const agentName = script.getAttribute("data-agent-name") || undefined;
    const welcome = script.getAttribute("data-welcome") || undefined;
    const promptsAttr = script.getAttribute("data-prompts");
    const suggestedPrompts = promptsAttr
      ? promptsAttr.split("|").map((s) => s.trim()).filter(Boolean)
      : undefined;
    const locale = script.getAttribute("data-locale") || undefined;
    const leadCapture = script.getAttribute("data-lead-capture") === "true";
    const enableHandoff = script.getAttribute("data-handoff") !== "false";

    return new Widget({
      apiKey,
      apiBaseUrl: script.getAttribute("data-api-url") || detectBaseUrl(script),
      position,
      agentName,
      welcomeMessage: welcome,
      suggestedPrompts,
      locale,
      leadCapture,
      enableHandoff,
      theme: {
        mode: themeMode,
        primaryColor: primary,
      },
    });
  }

  // ── Public API ────────────────────────────────────────────────────────────

  open = (): void => {
    if (this.destroyed || this.openState) return;
    this.openState = true;
    this.panel.classList.add("is-open");
    this.panel.setAttribute("aria-hidden", "false");
    this.launcher.setAttribute("aria-expanded", "true");
    this.unread = 0;
    this.renderBadge();
    this.inputEl.focus();
    this.options.onOpen?.();
  };

  close = (): void => {
    if (this.destroyed || !this.openState) return;
    this.openState = false;
    this.panel.classList.remove("is-open");
    this.panel.setAttribute("aria-hidden", "true");
    this.launcher.setAttribute("aria-expanded", "false");
    this.launcher.focus();
    this.options.onClose?.();
  };

  toggle = (): void => {
    this.openState ? this.close() : this.open();
  };

  isOpen = (): boolean => this.openState;

  setTheme = (theme: Partial<WidgetTheme> | WidgetThemeMode): void => {
    this.theme = mergeTheme(this.theme, theme);
    applyThemeVars(this.root, this.theme);
  };

  identifyUser = (user: Record<string, unknown>): void => {
    this.userMeta = { ...this.userMeta, ...user };
  };

  destroy = (): void => {
    if (this.destroyed) return;
    this.destroyed = true;
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.mediaQuery && this.onMediaChange) {
      this.mediaQuery.removeEventListener("change", this.onMediaChange);
    }
    this.root.remove();
  };

  sendMessage = async (text: string): Promise<void> => {
    const content = text.trim();
    if (!content || this.busy || this.destroyed) return;

    if (this.options.leadCapture === true && !this.leadCaptured) {
      this.showLeadForm();
      return;
    }

    this.open();
    this.busy = true;
    this.sendBtn.disabled = true;
    this.hideWelcome();

    const userMsg: ChatMessage = {
      id: uid("u"),
      role: "user",
      content,
      createdAt: Date.now(),
    };
    this.pushMessage(userMsg);
    this.options.onMessage?.(userMsg);

    const thinking = this.showThinking(this.strings.thinking);
    const assistantId = uid("a");
    let assistantEl: HTMLElement | null = null;

    try {
      let streamed = false;
      let finalReply = "";
      let conversationId = this.conversationId;

      for await (const event of this.client.streamChat(
        content,
        this.conversationId,
        this.userMeta
      )) {
        streamed = true;
        if (event.type === "thinking") {
          const label = thinking.querySelector(".tht-thinking-label");
          if (label) label.textContent = event.message || this.strings.thinking;
          thinking.classList.add("is-thinking");
        } else if (event.type === "token") {
          if (!assistantEl) {
            thinking.remove();
            assistantEl = this.appendBubble("assistant", "", assistantId);
          }
          finalReply += event.text;
          assistantEl.textContent = finalReply;
          this.scrollToBottom();
        } else if (event.type === "done") {
          conversationId = event.conversation_id || conversationId;
          finalReply = event.reply || finalReply;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }

      if (!streamed) {
        const res = await this.client.chat(
          content,
          this.conversationId,
          this.userMeta
        );
        conversationId = res.conversation_id;
        finalReply = res.reply;
        thinking.remove();
        assistantEl = this.appendBubble("assistant", "", assistantId);
        await this.revealText(assistantEl, finalReply);
      } else if (!assistantEl) {
        thinking.remove();
        assistantEl = this.appendBubble("assistant", finalReply, assistantId);
      } else {
        assistantEl.textContent = finalReply;
      }

      if (conversationId) {
        this.conversationId = conversationId;
        saveSession(this.options.apiKey, conversationId);
      }

      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: finalReply,
        createdAt: Date.now(),
      };
      this.messages.push(assistantMsg);
      saveHistory(this.options.apiKey, this.messages);
      this.options.onMessage?.(assistantMsg);

      if (!this.openState) {
        this.unread += 1;
        this.renderBadge();
      }
    } catch (err) {
      thinking.remove();
      const error = err instanceof Error ? err : new Error(String(err));
      this.appendBubble("assistant", error.message || "Something went wrong.");
      this.options.onError?.(error);
    } finally {
      this.busy = false;
      this.sendBtn.disabled = false;
      this.inputEl.focus();
    }
  };

  // ── Mount / UI ────────────────────────────────────────────────────────────

  private mount(): void {
    this.root = document.createElement("div");
    this.root.className = `tht-root tht-pos-${this.options.position || "bottom-right"}`;
    this.root.style.zIndex = String(this.options.zIndex || 2147483000);
    this.shadow = this.root.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = styles;
    this.shadow.appendChild(style);

    const wrap = document.createElement("div");
    wrap.innerHTML = this.template();
    this.shadow.appendChild(wrap);

    document.body.appendChild(this.root);
    applyThemeVars(this.root, this.theme);

    this.panel = this.shadow.querySelector(".tht-panel") as HTMLElement;
    this.messagesEl = this.shadow.querySelector(".tht-messages") as HTMLElement;
    this.inputEl = this.shadow.querySelector(".tht-input") as HTMLTextAreaElement;
    this.sendBtn = this.shadow.querySelector(".tht-send") as HTMLButtonElement;
    this.launcher = this.shadow.querySelector(".tht-launcher") as HTMLButtonElement;
    this.badgeEl = this.shadow.querySelector(".tht-badge") as HTMLSpanElement;

    this.bindEvents();
    this.restoreMessages();
    this.renderBadge();

    if (this.theme.mode === "auto") {
      this.mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      this.onMediaChange = () => applyThemeVars(this.root, this.theme);
      this.mediaQuery.addEventListener("change", this.onMediaChange);
    }
  }

  private template(): string {
    const s = this.strings;
    const logo = this.theme.logoUrl
      ? `<img class="tht-logo" src="${this.escape(this.theme.logoUrl)}" alt="" />`
      : this.theme.avatarUrl
        ? `<img class="tht-avatar" src="${this.escape(this.theme.avatarUrl)}" alt="" />`
        : `<div class="tht-avatar" aria-hidden="true"></div>`;

    const prompts = (this.options.suggestedPrompts || [])
      .map(
        (p) =>
          `<button type="button" class="tht-prompt" data-prompt="${this.escape(p)}">${this.escape(p)}</button>`
      )
      .join("");

    const handoffBtn =
      this.options.enableHandoff === false
        ? ""
        : `<button type="button" class="tht-handoff">${this.escape(s.talkToHuman)}</button>`;

    return `
      <button type="button" class="tht-launcher" aria-label="${this.escape(s.openChat)}" aria-expanded="false" aria-controls="tht-panel">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H9l-4 4v-4.5A2.5 2.5 0 0 1 4 13.5v-8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        </svg>
        <span class="tht-badge" hidden>0</span>
      </button>
      <section class="tht-panel" id="tht-panel" role="dialog" aria-modal="true" aria-label="Chat" aria-hidden="true">
        <header class="tht-header">
          ${logo}
          <div class="tht-header-meta">
            <p class="tht-agent-name">${this.escape(this.options.agentName || "AI Assistant")}</p>
            <p class="tht-status"><span class="tht-dot" aria-hidden="true"></span>${this.escape(s.online)}</p>
          </div>
          <button type="button" class="tht-icon-btn tht-minimize" aria-label="${this.escape(s.minimize)}">─</button>
          <button type="button" class="tht-icon-btn tht-close" aria-label="${this.escape(s.closeChat)}">✕</button>
        </header>
        <div class="tht-messages" role="log" aria-live="polite">
          <div class="tht-welcome">
            <h3>${this.escape(s.welcomeTitle)}</h3>
            <p>${this.escape(this.options.welcomeMessage || "Hi! How can I help you today?")}</p>
            <div class="tht-prompts">${prompts}</div>
          </div>
        </div>
        <div class="tht-actions">${handoffBtn}</div>
        <form class="tht-composer">
          <textarea class="tht-input" rows="1" placeholder="${this.escape(s.placeholder)}" aria-label="Message"></textarea>
          <button type="submit" class="tht-send">${this.escape(s.send)}</button>
        </form>
      </section>
    `;
  }

  private bindEvents(): void {
    this.launcher.addEventListener("click", () => this.toggle());
    this.shadow.querySelector(".tht-close")?.addEventListener("click", () => this.close());
    this.shadow.querySelector(".tht-minimize")?.addEventListener("click", () => this.close());

    const form = this.shadow.querySelector(".tht-composer") as HTMLFormElement;
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const value = this.inputEl.value;
      this.inputEl.value = "";
      void this.sendMessage(value);
    });

    this.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });

    this.shadow.querySelectorAll(".tht-prompt").forEach((btn) => {
      btn.addEventListener("click", () => {
        const prompt = (btn as HTMLElement).dataset.prompt || "";
        void this.sendMessage(prompt);
      });
    });

    this.shadow.querySelector(".tht-handoff")?.addEventListener("click", () => {
      void this.requestHuman();
    });

    this.shadow.addEventListener("keydown", (e: Event) => {
      const ke = e as KeyboardEvent;
      if (ke.key === "Escape" && this.openState) {
        ke.stopPropagation();
        this.close();
      }
      if (ke.key === "Tab" && this.openState) {
        this.trapFocus(ke);
      }
    });
  }

  private trapFocus(e: KeyboardEvent): void {
    this.focusables = Array.from(
      this.shadow.querySelectorAll<HTMLElement>(
        'button, [href], textarea, input, select, [tabindex]:not([tabindex="-1"])'
      )
    ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);

    if (!this.focusables.length) return;
    const first = this.focusables[0];
    const last = this.focusables[this.focusables.length - 1];
    const active = this.shadow.activeElement as HTMLElement | null;

    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  private restoreMessages(): void {
    if (!this.messages.length) return;
    this.hideWelcome();
    for (const msg of this.messages) {
      const role = msg.role === "user" ? "user" : msg.role === "human" ? "human" : "assistant";
      this.appendBubble(role, msg.content, msg.id);
      this.lastMessageId = msg.id;
    }
  }

  private pushMessage(msg: ChatMessage): void {
    this.messages.push(msg);
    const role = msg.role === "user" ? "user" : msg.role === "human" ? "human" : "assistant";
    this.appendBubble(role, msg.content, msg.id);
    saveHistory(this.options.apiKey, this.messages);
  }

  private appendBubble(
    role: "user" | "assistant" | "human",
    content: string,
    id?: string
  ): HTMLElement {
    const el = document.createElement("div");
    el.className = `tht-msg ${role === "human" ? "assistant human" : role}`;
    if (id) el.dataset.id = id;
    el.textContent = content;
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  }

  private showTyping(): HTMLElement {
    return this.showThinking(this.strings.thinking);
  }

  private showThinking(label: string): HTMLElement {
    const el = document.createElement("div");
    el.className = "tht-typing tht-thinking";
    el.setAttribute("aria-label", label);
    el.innerHTML = `<span class="tht-thinking-label">${this.escape(label)}</span><span></span><span></span><span></span>`;
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  }

  private showLeadForm(): void {
    if (this.shadow.querySelector(".tht-lead")) {
      this.open();
      return;
    }
    this.open();
    this.hideWelcome();
    const s = this.strings;
    const form = document.createElement("form");
    form.className = "tht-lead";
    form.innerHTML = `
      <h4>${this.escape(s.leadTitle)}</h4>
      <input name="name" placeholder="${this.escape(s.leadName)}" autocomplete="name" />
      <input name="email" type="email" placeholder="${this.escape(s.leadEmail)}" autocomplete="email" />
      <input name="phone" type="tel" placeholder="${this.escape(s.leadPhone)}" autocomplete="tel" />
      <div class="tht-lead-actions">
        <button type="submit">${this.escape(s.leadSubmit)}</button>
        <button type="button" class="tht-lead-skip">${this.escape(s.leadSkip)}</button>
      </div>
    `;
    this.messagesEl.appendChild(form);
    form.querySelector(".tht-lead-skip")?.addEventListener("click", () => {
      this.leadCaptured = true;
      form.remove();
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const lead = {
        name: String(fd.get("name") || "").trim(),
        email: String(fd.get("email") || "").trim(),
        phone: String(fd.get("phone") || "").trim(),
        source: "widget",
      };
      void this.submitLead(lead).finally(() => {
        this.leadCaptured = true;
        form.remove();
      });
    });
  }

  private async submitLead(lead: Record<string, string>): Promise<void> {
    try {
      const res = await this.client.captureLead(this.conversationId, lead, this.userMeta);
      this.userMeta = { ...this.userMeta, lead, email: lead.email, name: lead.name };
      if (res.conversation_id) {
        this.conversationId = res.conversation_id;
        saveSession(this.options.apiKey, res.conversation_id);
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      this.options.onError?.(error);
    }
  }

  private async requestHuman(): Promise<void> {
    if (!this.conversationId) {
      await this.sendMessage("I'd like to talk to a human");
      return;
    }
    try {
      await this.client.requestHandoff(this.conversationId, this.strings.talkToHuman);
      this.appendBubble("assistant", this.strings.talkToHuman + " — connecting…");
    } catch (err) {
      await this.sendMessage("talk to a human");
    }
  }

  private startPolling(): void {
    if (this.pollTimer) return;
    this.pollTimer = setInterval(() => {
      void this.pollHumanReplies();
    }, 4000);
  }

  private async pollHumanReplies(): Promise<void> {
    if (!this.conversationId || this.destroyed || this.busy) return;
    try {
      const res = await this.client.sessionMessages(this.conversationId, this.lastMessageId);
      for (const m of res.messages || []) {
        if (m.role !== "human") {
          this.lastMessageId = m.id;
          continue;
        }
        if (this.messages.some((x) => x.id === m.id)) {
          this.lastMessageId = m.id;
          continue;
        }
        const msg: ChatMessage = {
          id: m.id,
          role: "human",
          content: m.content,
          createdAt: Date.now(),
        };
        this.messages.push(msg);
        this.appendBubble("human", m.content, m.id);
        saveHistory(this.options.apiKey, this.messages);
        this.lastMessageId = m.id;
        if (!this.openState) {
          this.unread += 1;
          this.renderBadge();
        }
      }
    } catch {
      /* ignore poll errors */
    }
  }

  private hideWelcome(): void {
    this.shadow.querySelector(".tht-welcome")?.remove();
  }

  private renderBadge(): void {
    if (this.unread > 0 && !this.openState) {
      this.badgeEl.hidden = false;
      this.badgeEl.textContent = this.unread > 9 ? "9+" : String(this.unread);
    } else {
      this.badgeEl.hidden = true;
    }
  }

  private scrollToBottom(): void {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  private async revealText(el: HTMLElement, text: string): Promise<void> {
    const chunk = Math.max(1, Math.ceil(text.length / 40));
    let i = 0;
    while (i < text.length) {
      i = Math.min(text.length, i + chunk);
      el.textContent = text.slice(0, i);
      this.scrollToBottom();
      await new Promise((r) => setTimeout(r, 16));
    }
  }

  private escape(value: string): string {
    return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** Test helper */
  resetSession(): void {
    clearSession(this.options.apiKey);
    this.conversationId = null;
    this.messages = [];
  }
}
