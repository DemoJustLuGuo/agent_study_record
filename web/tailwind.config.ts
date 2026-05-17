import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        console: {
          bg: "#0f172a",
          surface: "#1e293b",
          panel: "#1e293b",
          muted: "#334155",
          border: "#475569",
          text: "#f8fafc",
          subdued: "#94a3b8",
          accent: "#22c55e",
          warn: "#f59e0b",
          danger: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["'Nunito Sans'", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'Fira Code'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        panel: "0 20px 40px -10px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(255, 255, 255, 0.05) inset",
      },
    },
  },
  plugins: [],
} satisfies Config;
