import type { Config } from "tailwindcss"

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        panel: "0 18px 55px rgba(15, 23, 42, 0.08)",
      },
      colors: {
        trail: {
          ink: "#172033",
          muted: "#667085",
          surface: "#f6f8fb",
          strava: "#fc4c02",
        },
        brand: {
          void: "#050505",
          charcoal: "#0a0c0e",
          /** Primary accent — ~15.7:1 on void */
          teal: "#00ffd1",
          /** Secondary accent — ~17:1 on void */
          lime: "#ccff00",
          /** Body / captions on dark (~9.7:1 on void vs old #8a9399 ~6.5:1) */
          muted: "#a9b4be",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config
