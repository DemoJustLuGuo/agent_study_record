import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        console: {
          bg: "#020617",
          surface: "#0f172a",
          panel: "#111827",
          muted: "#1e293b",
          border: "#334155",
          text: "#f8fafc",
          subdued: "#94a3b8",
          accent: "#22c55e",
          warn: "#f59e0b",
          danger: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Fira Code", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        panel: "0 18px 45px rgba(2, 6, 23, 0.36)",
      },
    },
  },
  plugins: [],
} satisfies Config;
