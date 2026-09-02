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
  ImageContentBlock,
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

const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_IMAGE_BYTES = 8 * 1024 * 1024; // 8MB — generous for a chat attachment, well under typical upload limits
const MAX_RECORDING_MS = 120_000; // safety cap so a forgotten-open mic can't record forever

const RECORDER_MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

function pickRecorderMimeType(): string {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  return RECORDER_MIME_CANDIDATES.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

function voiceSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia) &&
    typeof MediaRecorder !== "undefined"
  );
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
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

  // Voice input
  private fileInput?: HTMLInputElement;
  private micBtnEl?: HTMLButtonElement;
  private attachBtnEl?: HTMLButtonElement;
  private imageGenBtnEl?: HTMLButtonElement;
  private recordingBar?: HTMLElement;
  private recTimeEl?: HTMLElement;
  private mediaRecorder: MediaRecorder | null = null;
  private mediaStream: MediaStream | null = null;
  private recordedChunks: BlobPart[] = [];
  private recordingStartedAt = 0;
  private recordingTimer?: ReturnType<typeof setInterval>;
  private isRecording = false;

  // Vision (image attach)
  private attachmentPreviewEl?: HTMLElement;
  private attachmentThumbEl?: HTMLImageElement;
  private pendingImage: ImageContentBlock | null = null;

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

    // One-shot capability discovery for new-style embeds (data-agent-slug +
    // api key, no explicit data-voice/data-vision/data-image-generation).
    // Never polls — see loadCapabilitiesFromConfig.
    if (
      this.options.agentSlug &&
      (this.options.voiceEnabled === undefined ||
        this.options.visionEnabled === undefined ||
        this.options.imageGenerationEnabled === undefined)
    ) {
      void this.loadCapabilitiesFromConfig();
    }
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
    const agentSlug = script.getAttribute("data-agent-slug") || undefined;
    // Only set these from an *explicit* attribute — its absence leaves the
    // option `undefined` so the widget can fill it in from the fetched
    // widget-config instead (see Widget.loadCapabilitiesFromConfig). A
    // legacy embed that does set data-voice/data-vision/data-image-generation
    // keeps behaving exactly as before: that explicit value always wins.
    const voiceEnabled = script.hasAttribute("data-voice")
      ? script.getAttribute("data-voice") === "true"
      : undefined;
    const visionEnabled = script.hasAttribute("data-vision")
      ? script.getAttribute("data-vision") === "true"
      : undefined;
    const imageGenerationEnabled = script.hasAttribute("data-image-generation")
      ? script.getAttribute("data-image-generation") === "true"
      : undefined;

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
      agentSlug,
      voiceEnabled,
      visionEnabled,
      imageGenerationEnabled,
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
    if (this.isRecording) {
      this.mediaRecorder?.stop();
      this.teardownRecording();
    }
    this.root.remove();
  };

  sendMessage = async (text: string): Promise<void> => {
    const content = text.trim();
    const imageToSend = this.pendingImage;
    if ((!content && !imageToSend) || this.busy || this.destroyed) return;

    if (this.options.leadCapture === true && !this.leadCaptured) {
      this.showLeadForm();
      return;
    }

    this.clearPendingImage();
    this.open();
    this.setComposerBusy(true);
    this.hideWelcome();

    const userMsg: ChatMessage = {
      id: uid("u"),
      role: "user",
      content: content || (imageToSend ? "[Image attached]" : ""),
      createdAt: Date.now(),
    };
    this.messages.push(userMsg);
    saveHistory(this.options.apiKey, this.messages);
    if (imageToSend) {
      this.appendUserImageBubble(imageToSend.image_url.url, content, userMsg.id);
    } else {
      this.appendBubble("user", userMsg.content, userMsg.id);
    }
    this.options.onMessage?.(userMsg);

    const thinking = this.showThinking(this.strings.thinking);
    const assistantId = uid("a");
    let assistantEl: HTMLElement | null = null;
    const images = imageToSend ? [imageToSend] : undefined;

    try {
      let streamed = false;
      let finalReply = "";
      let conversationId = this.conversationId;

      for await (const event of this.client.streamChat(
        content,
        this.conversationId,
        this.userMeta,
        images
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
          this.userMeta,
          images
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
      this.setComposerBusy(false);
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
    this.fileInput = this.shadow.querySelector(".tht-file-input") as HTMLInputElement | undefined;
    this.recordingBar = this.shadow.querySelector(".tht-recording") as HTMLElement;
    this.recTimeEl = this.shadow.querySelector(".tht-rec-time") as HTMLElement;
    this.attachmentPreviewEl = this.shadow.querySelector(".tht-attachment-preview") as HTMLElement;
    this.attachmentThumbEl = this.shadow.querySelector(".tht-attachment-thumb") as HTMLImageElement;
    this.micBtnEl = this.shadow.querySelector(".tht-mic") as HTMLButtonElement | undefined;
    this.attachBtnEl = this.shadow.querySelector(".tht-attach") as HTMLButtonElement | undefined;
    this.imageGenBtnEl = this.shadow.querySelector(".tht-imagegen") as HTMLButtonElement | undefined;

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
        <div class="tht-composer-wrap">
          <div class="tht-attachment-preview" hidden>
            <img class="tht-attachment-thumb" alt="" />
            <button type="button" class="tht-attachment-remove" aria-label="${this.escape(s.removeImage)}">✕</button>
          </div>
          <div class="tht-recording" hidden>
            <span class="tht-rec-dot" aria-hidden="true"></span>
            <span class="tht-rec-time">0:00</span>
            <span class="tht-rec-label">${this.escape(s.recording)}</span>
            <button type="button" class="tht-rec-cancel" aria-label="${this.escape(s.cancelRecording)}">✕</button>
            <button type="button" class="tht-rec-stop" aria-label="${this.escape(s.stopRecording)}">
              <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>
            </button>
          </div>
          <form class="tht-composer">
            ${this.renderComposerExtras()}
            <textarea class="tht-input" rows="1" placeholder="${this.escape(s.placeholder)}" aria-label="Message"></textarea>
            <button type="submit" class="tht-send">${this.escape(s.send)}</button>
          </form>
        </div>
      </section>
    `;
  }

  /**
   * Mic / attach / image-generation buttons + hidden file input — extracted
   * so they can be re-rendered after `loadCapabilitiesFromConfig` resolves
   * (fetched capabilities arrive asynchronously, after the initial mount).
   */
  private renderComposerExtras(): string {
    const s = this.strings;

    const micBtn =
      this.options.voiceEnabled && voiceSupported()
        ? `<button type="button" class="tht-composer-btn tht-mic" aria-label="${this.escape(s.micLabel)}" title="${this.escape(s.micLabel)}">
             <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
               <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Z" stroke="currentColor" stroke-width="1.8"/>
               <path d="M19 11a7 7 0 0 1-14 0M12 18v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
             </svg>
           </button>`
        : "";

    const attachBtn = this.options.visionEnabled
      ? `<button type="button" class="tht-composer-btn tht-attach" aria-label="${this.escape(s.attachImageLabel)}" title="${this.escape(s.attachImageLabel)}">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
             <rect x="3.5" y="4.5" width="17" height="15" rx="2" stroke="currentColor" stroke-width="1.8"/>
             <circle cx="8.5" cy="9.5" r="1.5" stroke="currentColor" stroke-width="1.5"/>
             <path d="m5 16 4.5-4.5a2 2 0 0 1 2.8 0L15 14.2m2-2 2.5 2.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
           </svg>
         </button>`
      : "";

    const imageGenBtn = this.options.imageGenerationEnabled
      ? `<button type="button" class="tht-composer-btn tht-imagegen" aria-label="${this.escape(s.generateImageLabel)}" title="${this.escape(s.generateImageLabel)}">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
             <path d="M12 4v4M12 16v4M4 12h4M16 12h4M6.5 6.5l2 2M15.5 15.5l2 2M17.5 6.5l-2 2M8.5 15.5l-2 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
           </svg>
         </button>`
      : "";

    const fileInput = this.options.visionEnabled
      ? `<input type="file" class="tht-file-input" accept="${ACCEPTED_IMAGE_TYPES.join(",")}" hidden />`
      : "";

    return `${micBtn}${attachBtn}${imageGenBtn}${fileInput}`;
  }

  /**
   * Fetch /public/v1/agents/{slug}/widget-config once and fill in any of
   * voiceEnabled/visionEnabled/imageGenerationEnabled that weren't set
   * explicitly (via data-* attributes). Re-renders just the composer's
   * optional buttons — never touches messages, input value, or open state.
   * No polling: this runs exactly once, from the constructor.
   */
  private async loadCapabilitiesFromConfig(): Promise<void> {
    const slug = this.options.agentSlug;
    if (!slug) return;
    const config = await this.client.getWidgetConfig(slug);
    if (!config || this.destroyed) return;

    const caps = config.capabilities;
    let changed = false;
    if (this.options.voiceEnabled === undefined) {
      this.options.voiceEnabled = Boolean(caps.voice);
      changed = true;
    }
    if (this.options.visionEnabled === undefined) {
      this.options.visionEnabled = Boolean(caps.vision);
      changed = true;
    }
    if (this.options.imageGenerationEnabled === undefined) {
      this.options.imageGenerationEnabled = Boolean(caps.image_generation);
      changed = true;
    }
    if (changed) this.refreshComposerExtras();
  }

  /** Re-renders the mic/attach/image-generation buttons + file input in place
   * and rebinds their listeners — used after capabilities load asynchronously. */
  private refreshComposerExtras(): void {
    const form = this.shadow.querySelector(".tht-composer") as HTMLFormElement | null;
    if (!form) return;
    form.querySelectorAll(".tht-mic, .tht-attach, .tht-imagegen, .tht-file-input").forEach((el) => el.remove());
    form.insertAdjacentHTML("afterbegin", this.renderComposerExtras());

    this.fileInput = this.shadow.querySelector(".tht-file-input") as HTMLInputElement | undefined;
    this.micBtnEl = this.shadow.querySelector(".tht-mic") as HTMLButtonElement | undefined;
    this.attachBtnEl = this.shadow.querySelector(".tht-attach") as HTMLButtonElement | undefined;
    this.imageGenBtnEl = this.shadow.querySelector(".tht-imagegen") as HTMLButtonElement | undefined;
    this.bindComposerExtrasEvents();
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

    this.shadow.querySelector(".tht-rec-stop")?.addEventListener("click", () => {
      void this.stopRecordingAndSend();
    });
    this.shadow.querySelector(".tht-rec-cancel")?.addEventListener("click", () => {
      this.cancelRecording();
    });
    this.shadow.querySelector(".tht-attachment-remove")?.addEventListener("click", () => {
      this.clearPendingImage();
    });

    this.bindComposerExtrasEvents();

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

  /** Binds the mic/attach/image-generation/file-input listeners against
   * whatever elements currently match those selectors. Called from
   * `bindEvents` on initial mount and again from `refreshComposerExtras`
   * after capabilities load asynchronously and the buttons are re-rendered. */
  private bindComposerExtrasEvents(): void {
    this.shadow.querySelector(".tht-mic")?.addEventListener("click", () => {
      void this.startRecording();
    });
    this.shadow.querySelector(".tht-attach")?.addEventListener("click", () => {
      this.fileInput?.click();
    });
    this.fileInput?.addEventListener("change", () => {
      const file = this.fileInput?.files?.[0];
      if (file) void this.handleFileSelected(file);
      if (this.fileInput) this.fileInput.value = "";
    });
    this.shadow.querySelector(".tht-imagegen")?.addEventListener("click", () => {
      void this.generateImageFromPrompt();
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

  // ── Voice input ──────────────────────────────────────────────────────────

  private async startRecording(): Promise<void> {
    if (this.isRecording || this.busy || this.destroyed) return;
    if (!voiceSupported()) {
      this.appendBubble("assistant", this.strings.micUnavailable);
      return;
    }

    let stream: MediaStream;
    try {
      // Permission is requested here, on click — never before.
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      this.appendBubble("assistant", this.strings.micPermissionDenied);
      this.options.onError?.(err instanceof Error ? err : new Error(String(err)));
      return;
    }

    const mimeType = pickRecorderMimeType();
    let recorder: MediaRecorder;
    try {
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    } catch (err) {
      stream.getTracks().forEach((t) => t.stop());
      this.appendBubble("assistant", this.strings.micUnavailable);
      return;
    }

    this.mediaStream = stream;
    this.mediaRecorder = recorder;
    this.recordedChunks = [];
    this.isRecording = true;
    this.recordingStartedAt = Date.now();

    recorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size > 0) this.recordedChunks.push(e.data);
    });

    // A timeslice makes `dataavailable` fire periodically during recording
    // instead of relying solely on the single flush-on-stop event. Without
    // it, a short recording (or certain browser/codec combinations) can
    // legitimately deliver an empty final chunk on stop() — with no
    // periodic chunks to fall back on, recordedChunks ends up empty and
    // the turn silently never gets sent (see stopRecordingAndSend below).
    recorder.start(250);
    this.showRecordingUI(true);
    this.recordingTimer = setInterval(() => {
      const elapsed = Date.now() - this.recordingStartedAt;
      if (this.recTimeEl) this.recTimeEl.textContent = formatElapsed(elapsed);
      if (elapsed >= MAX_RECORDING_MS) void this.stopRecordingAndSend();
    }, 250);
  }

  private teardownRecording(): void {
    if (this.recordingTimer) {
      clearInterval(this.recordingTimer);
      this.recordingTimer = undefined;
    }
    this.mediaStream?.getTracks().forEach((t) => t.stop());
    this.mediaStream = null;
    this.mediaRecorder = null;
    this.isRecording = false;
    this.showRecordingUI(false);
  }

  private cancelRecording(): void {
    if (!this.isRecording) return;
    this.recordedChunks = [];
    this.mediaRecorder?.stop();
    this.teardownRecording();
  }

  private async stopRecordingAndSend(): Promise<void> {
    if (!this.isRecording || !this.mediaRecorder) return;
    const recorder = this.mediaRecorder;
    const mimeType = recorder.mimeType || "audio/webm";
    // Guard immediately (before the first await) so a rapid double
    // click/tap on Stop can't re-enter and call recorder.stop() twice.
    this.isRecording = false;

    try {
      const stopped = new Promise<void>((resolve) => {
        recorder.addEventListener("stop", () => resolve(), { once: true });
      });
      recorder.stop();
      await stopped;
    } catch (err) {
      this.teardownRecording();
      this.appendBubble("assistant", this.strings.voiceRequestFailed);
      this.options.onError?.(err instanceof Error ? err : new Error(String(err)));
      return;
    }
    this.teardownRecording();

    if (!this.recordedChunks.length) {
      // Never fail silently — a too-short recording (or a browser that
      // delivered an empty final chunk) must still tell the user something
      // happened, instead of the composer just going quiet.
      this.appendBubble("assistant", this.strings.recordingTooShort);
      return;
    }
    const blob = new Blob(this.recordedChunks, { type: mimeType });
    this.recordedChunks = [];
    await this.sendVoiceMessage(blob, mimeType);
  }

  private showRecordingUI(recording: boolean): void {
    const form = this.shadow.querySelector(".tht-composer") as HTMLElement | null;
    if (this.recordingBar) this.recordingBar.hidden = !recording;
    if (form) form.hidden = recording;
    if (this.recTimeEl) this.recTimeEl.textContent = "0:00";
  }

  private async sendVoiceMessage(audio: Blob, mimeType: string): Promise<void> {
    if (!this.options.agentSlug) {
      this.appendBubble("assistant", this.strings.voiceRequestFailed);
      return;
    }
    this.open();
    this.setComposerBusy(true);
    this.hideWelcome();

    const ext = mimeType.includes("mp4") ? "m4a" : mimeType.includes("ogg") ? "ogg" : "webm";
    const thinking = this.showThinking(this.strings.thinking);

    try {
      const res = await this.client.voiceChat(
        this.options.agentSlug,
        audio,
        `voice-message.${ext}`,
        this.conversationId
      );
      thinking.remove();

      const userMsg: ChatMessage = {
        id: uid("u"),
        role: "user",
        content: res.transcript || "🎤",
        createdAt: Date.now(),
      };
      this.pushMessage(userMsg);
      this.options.onMessage?.(userMsg);

      const audioUrl = `data:${res.audio_mime_type};base64,${res.audio_base64}`;
      this.appendAudioBubble(res.reply, audioUrl);

      if (res.conversation_id) {
        this.conversationId = res.conversation_id;
        saveSession(this.options.apiKey, res.conversation_id);
      }
      const assistantMsg: ChatMessage = {
        id: uid("a"),
        role: "assistant",
        content: res.reply,
        createdAt: Date.now(),
      };
      this.messages.push(assistantMsg);
      saveHistory(this.options.apiKey, this.messages);
      this.options.onMessage?.(assistantMsg);
    } catch (err) {
      thinking.remove();
      const error = err instanceof Error ? err : new Error(String(err));
      this.appendBubble("assistant", error.message || this.strings.voiceRequestFailed);
      this.options.onError?.(error);
    } finally {
      this.setComposerBusy(false);
    }
  }

  // ── Vision (image attach) ────────────────────────────────────────────────

  private async handleFileSelected(file: File): Promise<void> {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      this.appendBubble("assistant", this.strings.unsupportedImageType);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      this.appendBubble("assistant", this.strings.imageTooLarge);
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error || new Error("read failed"));
      reader.readAsDataURL(file);
    }).catch(() => null);
    if (!dataUrl) return;

    this.pendingImage = { type: "image_url", image_url: { url: dataUrl } };
    if (this.attachmentThumbEl) this.attachmentThumbEl.src = dataUrl;
    if (this.attachmentPreviewEl) this.attachmentPreviewEl.hidden = false;
    this.inputEl.focus();
  }

  private clearPendingImage(): void {
    this.pendingImage = null;
    if (this.attachmentPreviewEl) this.attachmentPreviewEl.hidden = true;
    if (this.attachmentThumbEl) this.attachmentThumbEl.src = "";
  }

  // ── Image generation ─────────────────────────────────────────────────────

  private async generateImageFromPrompt(): Promise<void> {
    const prompt = this.inputEl.value.trim();
    if (!prompt) {
      this.inputEl.focus();
      this.appendBubble("assistant", this.strings.imagePromptRequired);
      return;
    }
    if (!this.options.agentSlug || this.busy || this.destroyed) return;

    this.inputEl.value = "";
    this.open();
    this.setComposerBusy(true);
    this.hideWelcome();

    const userMsg: ChatMessage = { id: uid("u"), role: "user", content: prompt, createdAt: Date.now() };
    this.pushMessage(userMsg);
    this.options.onMessage?.(userMsg);

    const thinking = this.showThinking(this.strings.generatingImage);
    try {
      const res = await this.client.generateImage(
        this.options.agentSlug,
        prompt,
        this.conversationId,
        this.userMeta
      );
      thinking.remove();

      const image = res.images?.[0];
      if (!image) throw new Error(this.strings.voiceRequestFailed);
      const src = image.data_base64
        ? `data:${image.mime_type};base64,${image.data_base64}`
        : image.url || "";
      this.appendImageBubble(src, image.revised_prompt || undefined);

      if (res.conversation_id) {
        this.conversationId = res.conversation_id;
        saveSession(this.options.apiKey, res.conversation_id);
      }
      const assistantMsg: ChatMessage = {
        id: uid("a"),
        role: "assistant",
        content: image.revised_prompt ? `[Image] ${image.revised_prompt}` : "[Image]",
        createdAt: Date.now(),
      };
      this.messages.push(assistantMsg);
      saveHistory(this.options.apiKey, this.messages);
      this.options.onMessage?.(assistantMsg);
    } catch (err) {
      thinking.remove();
      const error = err instanceof Error ? err : new Error(String(err));
      this.appendBubble("assistant", error.message || "Something went wrong.");
      this.options.onError?.(error);
    } finally {
      this.setComposerBusy(false);
      this.inputEl.focus();
    }
  }

  private appendUserImageBubble(src: string, caption: string, id?: string): HTMLElement {
    const el = document.createElement("div");
    el.className = "tht-msg user tht-msg-media";
    if (id) el.dataset.id = id;
    const img = document.createElement("img");
    img.className = "tht-msg-image";
    img.src = src;
    img.alt = "";
    el.appendChild(img);
    if (caption) {
      const p = document.createElement("p");
      p.className = "tht-msg-caption";
      p.textContent = caption;
      el.appendChild(p);
    }
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  }

  private appendImageBubble(src: string, caption?: string): HTMLElement {
    const el = document.createElement("div");
    el.className = "tht-msg assistant tht-msg-media";
    const img = document.createElement("img");
    img.className = "tht-msg-image";
    img.src = src;
    img.alt = caption || "";
    el.appendChild(img);
    if (caption) {
      const p = document.createElement("p");
      p.className = "tht-msg-caption";
      p.textContent = caption;
      el.appendChild(p);
    }
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  }

  private appendAudioBubble(replyText: string, audioSrc: string): HTMLElement {
    const el = document.createElement("div");
    el.className = "tht-msg assistant tht-msg-media";
    if (replyText) {
      const p = document.createElement("p");
      p.className = "tht-msg-caption";
      p.textContent = replyText;
      el.appendChild(p);
    }
    const audio = document.createElement("audio");
    audio.className = "tht-msg-audio";
    audio.controls = true;
    audio.src = audioSrc;
    el.appendChild(audio);
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    // Best-effort autoplay — the mic click that started this turn is the
    // user gesture; browsers may still block it after the network round
    // trip, in which case the visible controls let the user press play.
    void audio.play().catch(() => {
      /* autoplay blocked — controls remain visible */
    });
    return el;
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

  /** Disables/enables the send button AND the mic/attach/image-gen actions
   * together, so a reply/voice-turn/image-generation in flight can't be
   * interrupted by starting another one. */
  private setComposerBusy(busy: boolean): void {
    this.busy = busy;
    this.sendBtn.disabled = busy;
    if (this.micBtnEl) this.micBtnEl.disabled = busy;
    if (this.attachBtnEl) this.attachBtnEl.disabled = busy;
    if (this.imageGenBtnEl) this.imageGenBtnEl.disabled = busy;
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
