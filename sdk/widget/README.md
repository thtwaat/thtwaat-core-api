# @thtwaat/widget

Production embeddable AI chat widget for THTWAAT.

## One-line embed

```html
<script
  src="https://api.thtwaat.com/widget.js"
  data-api-key="tht_live_xxxxxxxxx"
  data-theme="light"
  data-position="bottom-right"
  data-primary-color="#111827"
  data-welcome="Hi! How can I help you today?"
  data-prompts="Pricing?|Book appointment|Contact support">
</script>
```

## Programmatic API

```js
const chat = window.THTWAAT.init({
  apiKey: "tht_live_xxx",
  apiBaseUrl: "https://api.thtwaat.com",
  theme: { mode: "dark", primaryColor: "#4f46e5" },
  onMessage: (m) => console.log(m),
});

chat.open();
chat.sendMessage("Hello");
chat.setTheme("light");
chat.identifyUser({ email: "user@acme.com" });
chat.close();
chat.destroy();
```

## Events

Pass handlers to `init`:

- `onReady`
- `onOpen`
- `onClose`
- `onMessage`
- `onError`

## Build

```bash
cd sdk/widget
npm install
npm run build
```

Outputs:

- `dist/widget.iife.js` — CDN / `/widget.js`
- `dist/widget.js` — ESM
- `dist/widget.umd.cjs` — CommonJS
- `dist/widget.css`
- copied to `app/agent_platform/static/widget/` for FastAPI

## Features

- Floating launcher + open/close animation
- Theme engine (light / dark / auto)
- Welcome message + suggested prompts
- Typing indicator
- Streaming via `/public/v1/chat/stream` (progressive fallback)
- Session persistence (`conversation_id` in localStorage)
- `window.THTWAAT` API
- Shadow DOM isolation
- Keyboard accessible (ESC, focus trap, ARIA)

See [EMBED.md](./EMBED.md) for framework examples.
