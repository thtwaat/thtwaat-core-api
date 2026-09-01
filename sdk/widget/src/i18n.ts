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
  micLabel: string;
  attachImageLabel: string;
  generateImageLabel: string;
  recording: string;
  stopRecording: string;
  cancelRecording: string;
  removeImage: string;
  generatingImage: string;
  imagePromptRequired: string;
  micPermissionDenied: string;
  micUnavailable: string;
  voiceRequestFailed: string;
  unsupportedImageType: string;
  imageTooLarge: string;
  recordingTooShort: string;
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
  leadSkip: "Skip",
  micLabel: "Record a voice message",
  attachImageLabel: "Attach an image",
  generateImageLabel: "Generate an image",
  recording: "Recording…",
  stopRecording: "Stop and send",
  cancelRecording: "Cancel",
  removeImage: "Remove image",
  generatingImage: "Generating image…",
  imagePromptRequired: "Type what you'd like to generate first.",
  micPermissionDenied: "Microphone access was denied. Enable it in your browser settings to use voice.",
  micUnavailable: "Voice recording isn't supported in this browser.",
  voiceRequestFailed: "Couldn't process that voice message. Please try again.",
  unsupportedImageType: "Please attach a PNG, JPEG, or WebP image.",
  imageTooLarge: "That image is too large. Please attach a smaller file.",
  recordingTooShort: "That recording was too short to send. Please try again and speak after starting."
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
  micLabel: "वॉइस संदेश रिकॉर्ड करें",
  attachImageLabel: "इमेज संलग्न करें",
  generateImageLabel: "इमेज जनरेट करें",
  recording: "रिकॉर्ड हो रहा है…",
  stopRecording: "रोकें और भेजें",
  cancelRecording: "रद्द करें",
  removeImage: "इमेज हटाएं",
  generatingImage: "इमेज बनाई जा रही है…",
  imagePromptRequired: "पहले बताएं आप क्या इमेज बनवाना चाहते हैं।",
  micPermissionDenied: "माइक्रोफ़ोन एक्सेस अस्वीकृत कर दिया गया। वॉइस इस्तेमाल करने के लिए इसे ब्राउज़र सेटिंग्स में सक्षम करें।",
  micUnavailable: "इस ब्राउज़र में वॉइस रिकॉर्डिंग समर्थित नहीं है।",
  voiceRequestFailed: "वह वॉइस संदेश प्रोसेस नहीं हो सका। कृपया फिर से कोशिश करें।",
  unsupportedImageType: "कृपया PNG, JPEG, या WebP इमेज संलग्न करें।",
  imageTooLarge: "यह इमेज बहुत बड़ी है। कृपया छोटी फ़ाइल संलग्न करें।",
  recordingTooShort: "वह रिकॉर्डिंग भेजने के लिए बहुत छोटी थी। कृपया दोबारा कोशिश करें और शुरू करने के बाद बोलें।",
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
