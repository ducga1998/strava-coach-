/**
 * Generates PWA icons from an emoji on a solid background.
 *
 * Run once from frontend/:
 *   node scripts/generate-icons.mjs
 *
 * Output: public/icon-192.png, icon-512.png, icon-512-maskable.png, apple-touch-icon.png
 *
 * To change the icon, edit EMOJI or BG below and re-run.
 */
import { chromium } from "playwright"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

const __dirname = dirname(fileURLToPath(import.meta.url))
const PUBLIC_DIR = resolve(__dirname, "..", "public")

const EMOJI = "🏔️"
const BG = "#050505" // matches tailwind brand.void

/**
 * Each spec: { name, size, padPct }
 *   padPct = padding around emoji as % of size. Maskable icons need ~20% safe-zone.
 */
const SPECS = [
  { name: "icon-192.png", size: 192, padPct: 0 },
  { name: "icon-512.png", size: 512, padPct: 0 },
  { name: "icon-512-maskable.png", size: 512, padPct: 20 },
  { name: "apple-touch-icon.png", size: 180, padPct: 0 },
]

const html = (size, padPct) => {
  // Emoji font-size = box size minus 2x padding, then 75% so glyph fits comfortably
  const inner = size * (1 - (padPct * 2) / 100)
  const fontSize = Math.floor(inner * 0.75)
  return `<!doctype html>
<html><head><style>
  html, body { margin: 0; padding: 0; }
  .box {
    width: ${size}px; height: ${size}px;
    background: ${BG};
    display: flex; align-items: center; justify-content: center;
    font-size: ${fontSize}px;
    line-height: 1;
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
  }
</style></head>
<body><div class="box">${EMOJI}</div></body></html>`
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ deviceScaleFactor: 1 })
const page = await ctx.newPage()

try {
  for (const { name, size, padPct } of SPECS) {
    await page.setViewportSize({ width: size, height: size })
    await page.setContent(html(size, padPct), { waitUntil: "load" })
    const out = resolve(PUBLIC_DIR, name)
    await page.locator(".box").screenshot({ path: out, omitBackground: false })
    console.log(`wrote ${out}`)
  }
} finally {
  await browser.close()
}
