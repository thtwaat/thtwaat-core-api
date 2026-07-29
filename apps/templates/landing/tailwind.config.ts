import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10231f",
        muted: "#63766f",
        cream: "#f6f5ef",
        mint: "#dff4ea",
        brand: "#136f63",
        accent: "#f2a65a"
      },
      boxShadow: {
        soft: "0 24px 80px -36px rgba(16,35,31,.35)"
      }
    }
  },
  plugins: []
};

export default config;
