import react from "@vitejs/plugin-react"
import { writeFileSync } from "node:fs"
import { resolve } from "node:path"
import { defineConfig, loadEnv } from "vite"
import { VitePWA } from "vite-plugin-pwa"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const siteUrl = env.VITE_SITE_URL?.replace(/\/$/, "") ?? ""

  return {
    plugins: [
      VitePWA({
        registerType: "autoUpdate",
        injectRegister: "auto",
        includeAssets: ["apple-touch-icon.png", "icon-192.png", "icon-512.png"],
        manifest: {
          name: "Strava AI Coach",
          short_name: "Coach",
          description: "AI debriefs and training load for trail/ultra runners",
          start_url: "/",
          scope: "/",
          display: "standalone",
          background_color: "#050505",
          theme_color: "#050505",
          orientation: "portrait",
          icons: [
            { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
            { src: "/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          ],
        },
        workbox: {
          skipWaiting: true,
          clientsClaim: true,
          // Default globPatterns precaches JS/CSS/HTML/SVG/PNG/ICO/woff2 — sufficient for this app.
        },
      }),
      react(),
      {
        name: "emit-sitemap-robots",
        closeBundle() {
          const outDir = resolve(process.cwd(), "dist")
          if (!siteUrl) {
            console.warn(
              "[emit-sitemap-robots] Set VITE_SITE_URL in .env.production to emit sitemap.xml and robots.txt Sitemap line."
            )
            return
          }
          const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${siteUrl}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>${siteUrl}/connect</loc>
    <changefreq>monthly</changefreq>
    <priority>0.85</priority>
  </url>
</urlset>
`
          writeFileSync(resolve(outDir, "sitemap.xml"), sitemap, "utf8")
          const robots = `User-agent: *
Allow: /

Sitemap: ${siteUrl}/sitemap.xml
`
          writeFileSync(resolve(outDir, "robots.txt"), robots, "utf8")
        },
      },
    ],
    server: {
      host: "0.0.0.0",
      port: 5173,
    },
  }
})
