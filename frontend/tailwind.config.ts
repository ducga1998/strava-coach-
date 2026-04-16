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
      },
    },
  },
  plugins: [],
} satisfies Config
