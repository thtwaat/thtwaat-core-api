/** Widget UI strings by locale (fallback English). */

export type WidgetLocalePack = {
  welcomeTitle: string;
  placeholder: string;
  send: string;
  openChat: string;
  closeChat: string;
  minimize: string;
  online: string;
  thinking: string;
  talkToHuman: string;
  leadTitle: string;
  leadName: string;
  leadEmail: string;
  leadPhone: string;
  leadSubmit: string;
  leadSkip: string;
};

const EN: WidgetLocalePack = {
  welcomeTitle: "Welcome",
  placeholder: "Type a message...",
  send: "Send",
  openChat: "Open chat",
  closeChat: "Close chat",
  minimize: "Minimize chat",
  online: "Online",
  thinking: "Thinking…",
  talkToHuman: "Talk to a human",
  leadTitle: "Before we start",
  leadName: "Name",
  leadEmail: "Email",
  leadPhone: "Phone",
  leadSubmit: "Continue",
  leadSkip: "Skip"
};

const HI: WidgetLocalePack = {
  ...EN,
  welcomeTitle: "स्वागत है",
  placeholder: "संदेश लिखें...",
  send: "भेजें",
  openChat: "चैट खोलें",
  closeChat: "चैट बंद करें",
  online: "ऑनलाइन",
  thinking: "सोच रहा है…",
  talkToHuman: "मानव से बात करें",
  leadTitle: "शुरू करने से पहले",
  leadName: "नाम",
  leadEmail: "ईमेल",
  leadPhone: "फ़ोन",
  leadSubmit: "जारी रखें",
  leadSkip: "छोड़ें"
};

const ES: WidgetLocalePack = {
  ...EN,
  welcomeTitle: "Bienvenido",
  placeholder: "Escribe un mensaje...",
  send: "Enviar",
  thinking: "Pensando…",
  talkToHuman: "Hablar con un humano",
  leadTitle: "Antes de empezar",
  leadSubmit: "Continuar",
  leadSkip: "Omitir"
};

const PACKS: Record<string, WidgetLocalePack> = {
  en: EN,
  hi: HI,
  es: ES
};

export function resolveWidgetLocale(code?: string | null): string {
  if (!code) {
    if (typeof navigator !== "undefined") {
      const lang = navigator.language || navigator.languages?.[0] || "en";
      return lang.split("-")[0].toLowerCase();
    }
    return "en";
  }
  return String(code).split("-")[0].toLowerCase();
}

export function widgetStrings(locale?: string | null): WidgetLocalePack {
  const code = resolveWidgetLocale(locale);
  return PACKS[code] || EN;
}
