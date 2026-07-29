import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        muted: "#64748b",
        canvas: "#f8fafc",
        panel: "#ffffff",
        line: "#e2e8f0",
        brand: {
          DEFAULT: "#0f766e",
          foreground: "#ffffff",
          soft: "#ccfbf1",
          dark: "#115e59"
        },
        accent: "#ea580c"
      },
      boxShadow: {
        soft: "0 10px 40px -20px rgba(15,23,42,.35)"
      }
    }
  },
  plugins: []
};

export default config;
