# PWA Installable Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Strava Coach frontend installable on iOS Safari and Android Chrome via the standard PWA install flow.

**Architecture:** Add `vite-plugin-pwa` (Workbox-based `generateSW` strategy) to the existing Vite config. Generate four PNG icons (192, 512, 512-maskable, 180) once via a Playwright-based Node script. Add iOS-specific meta tags to `index.html`. No changes to React app code.

**Tech Stack:** Vite 5, vite-plugin-pwa, Workbox, Playwright (already in devDeps for icon generation only).

**Spec:** `docs/superpowers/specs/2026-04-26-pwa-installable-design.md`

---

## File Structure

```
frontend/
├── package.json                  ← MODIFY: add vite-plugin-pwa
├── vite.config.ts                ← MODIFY: register VitePWA plugin
├── index.html                    ← MODIFY: add iOS meta tags + theme-color
├── scripts/
│   └── generate-icons.mjs        ← CREATE: one-shot Playwright icon generator
└── public/
    ├── icon-192.png              ← CREATE (output of generator)
    ├── icon-512.png              ← CREATE (output of generator)
    ├── icon-512-maskable.png     ← CREATE (output of generator)
    └── apple-touch-icon.png      ← CREATE (output of generator)
```

**No changes to** `src/`, backend, Cloudflare Pages config, tests.

---

### Task 1: Install `vite-plugin-pwa`

**Files:**
- Modify: `frontend/package.json` (devDependencies)

- [ ] **Step 1: Install the plugin**

Run from `frontend/`:

```bash
npm install -D vite-plugin-pwa@^0.20.5
```

Expected: `package.json` and `package-lock.json` updated. `vite-plugin-pwa` appears under `devDependencies`.

- [ ] **Step 2: Verify install**

```bash
npm ls vite-plugin-pwa
```

Expected: prints a version `0.20.x` with no `UNMET DEPENDENCY` errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add vite-plugin-pwa for installable PWA"
```

---

### Task 2: Create the icon-generator script

**Files:**
- Create: `frontend/scripts/generate-icons.mjs`

- [ ] **Step 1: Write the script**

Create `frontend/scripts/generate-icons.mjs` with this exact content:

```js
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

for (const { name, size, padPct } of SPECS) {
  await page.setViewportSize({ width: size, height: size })
  await page.setContent(html(size, padPct), { waitUntil: "load" })
  const out = resolve(PUBLIC_DIR, name)
  await page.locator(".box").screenshot({ path: out, omitBackground: false })
  console.log(`wrote ${out}`)
}

await browser.close()
```

- [ ] **Step 2: Ensure Playwright Chromium is installed**

Run from `frontend/`:

```bash
npx playwright install chromium
```

Expected: downloads Chromium if not already present. Idempotent — prints "is already installed" on subsequent runs.

- [ ] **Step 3: Run the generator**

Run from `frontend/`:

```bash
node scripts/generate-icons.mjs
```

Expected output (paths absolute on your machine):
```
wrote .../frontend/public/icon-192.png
wrote .../frontend/public/icon-512.png
wrote .../frontend/public/icon-512-maskable.png
wrote .../frontend/public/apple-touch-icon.png
```

- [ ] **Step 4: Verify output files**

```bash
ls -lh frontend/public/icon-*.png frontend/public/apple-touch-icon.png
file frontend/public/icon-192.png
```

Expected:
- All four files exist, non-zero size (~3–15 KB each).
- `file` reports `PNG image data, 192 x 192` for icon-192.

- [ ] **Step 5: Visual sanity check**

Open `frontend/public/icon-512.png` in Preview/Finder. Expected: dark `#050505` square with a centered mountain emoji. The maskable version has the emoji shrunk further from the edges (~20% inset on each side).

- [ ] **Step 6: Commit**

```bash
git add frontend/scripts/generate-icons.mjs frontend/public/icon-192.png frontend/public/icon-512.png frontend/public/icon-512-maskable.png frontend/public/apple-touch-icon.png
git commit -m "feat: add PWA icon generator and generated icons"
```

---

### Task 3: Register `vite-plugin-pwa` in `vite.config.ts`

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Add the import**

At the top of `frontend/vite.config.ts`, add this import alongside the existing imports:

```ts
import { VitePWA } from "vite-plugin-pwa"
```

- [ ] **Step 2: Register the plugin**

In `frontend/vite.config.ts`, the `plugins` array currently contains `react()` followed by the `emit-sitemap-robots` inline plugin. **Insert** the following `VitePWA({...})` block as the **first** entry of the `plugins` array (before `react()`). Do not delete or modify `react()` or the `emit-sitemap-robots` block — keep their existing bodies exactly as-is.

Block to insert (with a trailing comma — it goes before `react()`):

```ts
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
```

After the edit, the `plugins` array structure should be: `[VitePWA({...}), react(), { name: "emit-sitemap-robots", closeBundle() { /* existing body, unchanged */ } }]`.

- [ ] **Step 3: Typecheck**

Run from `frontend/`:

```bash
npm run typecheck
```

Expected: passes with no errors. (`vite-plugin-pwa` ships its own types.)

- [ ] **Step 4: Build**

Run from `frontend/`:

```bash
npm run build
```

Expected:
- Build succeeds.
- Console output mentions `PWA v0.20.x` and lists precached entries.
- `dist/manifest.webmanifest`, `dist/sw.js`, `dist/registerSW.js`, and `dist/workbox-*.js` exist.

- [ ] **Step 5: Verify manifest contents**

```bash
cat frontend/dist/manifest.webmanifest
```

Expected: JSON with `"name": "Strava AI Coach"`, `"display": "standalone"`, `"background_color": "#050505"`, and three icon entries.

- [ ] **Step 6: Verify SW references the icons**

```bash
grep -o "icon-[0-9]*[a-z-]*\.png" frontend/dist/sw.js | sort -u
```

Expected: prints `icon-192.png`, `icon-512.png`, `icon-512-maskable.png` (all three precached).

- [ ] **Step 7: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat: register vite-plugin-pwa with manifest and Workbox SW"
```

---

### Task 4: Add iOS meta tags to `index.html`

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Add the iOS + theme-color meta tags**

In `frontend/index.html`, find the existing `<meta name="description" ... />` line. Immediately **after** that meta tag and **before** the `<link rel="preconnect" ...>` lines, insert these five lines (preserving 4-space indent to match existing style):

```html
    <meta name="theme-color" content="#050505" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="Coach" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
```

The resulting `<head>` should contain (in order): charset, viewport, description, **theme-color**, **apple-mobile-web-app-capable**, **apple-mobile-web-app-status-bar-style**, **apple-mobile-web-app-title**, **apple-touch-icon**, preconnect (×2), Google Fonts link, title.

- [ ] **Step 2: Build**

Run from `frontend/`:

```bash
npm run build
```

Expected: build succeeds. `dist/index.html` contains the new meta tags AND a `vite-plugin-pwa`-injected line referencing `manifest.webmanifest` and `registerSW.js`.

- [ ] **Step 3: Verify dist HTML**

```bash
grep -E 'apple-touch-icon|apple-mobile-web-app|theme-color|manifest\.webmanifest|registerSW' frontend/dist/index.html
```

Expected: at minimum these matches —
- `<meta name="theme-color" content="#050505" />`
- `<meta name="apple-mobile-web-app-capable" content="yes" />`
- `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />`
- `<meta name="apple-mobile-web-app-title" content="Coach" />`
- `<link rel="apple-touch-icon" href="/apple-touch-icon.png" />`
- A `<link rel="manifest" href="/manifest.webmanifest">` (auto-injected by the plugin)
- A `<script ... src="/registerSW.js">` or inline `registerSW` script (auto-injected)

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add iOS PWA meta tags and theme-color"
```

---

### Task 5: Local install smoke-test (manual)

**Files:** none — this is verification only.

This task confirms the build is installable. It cannot be automated meaningfully because PWA install behavior is browser-specific.

- [ ] **Step 1: Build and serve**

Run from `frontend/`:

```bash
npm run build
npm run preview
```

Expected: Vite preview starts, prints `Local: http://localhost:4173/` and `Network: http://<your-lan-ip>:4173/`.

- [ ] **Step 2: Verify Lighthouse PWA criteria locally**

In Chrome desktop, open `http://localhost:4173/`. Open DevTools → Application tab → Manifest. Expected:
- Manifest loads with no errors.
- Name "Strava AI Coach", short name "Coach".
- Three icons listed, one marked maskable.
- "Installability" section reports the page is installable (no missing fields).

DevTools → Application → Service Workers. Expected: `sw.js` is `activated and is running`.

- [ ] **Step 3: Install on Android Chrome**

On an Android phone (same WiFi as the dev machine):

1. Open Chrome → navigate to `http://<your-lan-ip>:4173/`
2. Tap the three-dot menu → "Install app" or "Add to Home Screen"
3. Confirm install.

Expected: app icon appears on the home screen with the mountain emoji on dark background. Tapping it opens the app full-screen with no browser chrome.

- [ ] **Step 4: Install on iOS Safari**

On an iPhone (same WiFi as the dev machine):

1. Open Safari → navigate to `http://<your-lan-ip>:4173/`
2. Tap Share → "Add to Home Screen"
3. Confirm name shows as "Coach", icon previews as the mountain. Tap Add.

Expected: icon appears on the home screen. Tapping it opens the app full-screen with status bar in black-translucent style.

**Note:** iOS does NOT show an in-browser install prompt — this is iOS behavior, not a bug.

- [ ] **Step 5: Verify app reaches prod backend**

In the installed app (either platform), log in and load the dashboard. Expected: API calls succeed against the prod backend (configured via `VITE_API_URL` at build time).

If API calls fail with mixed-content or CORS errors, that's a separate config issue — out of scope for this plan; document the failure and stop.

- [ ] **Step 6: No commit**

This task produces no code changes. Move on to Task 6.

---

### Task 6: Production deploy verification

**Files:** none.

- [ ] **Step 1: Deploy via existing flow**

Run from `frontend/`:

```bash
npm run pages:deploy
```

Expected: Cloudflare Pages deploy succeeds. Output prints the deploy URL.

- [ ] **Step 2: Lighthouse PWA audit on the live URL**

In Chrome desktop, open the deployed URL. Open DevTools → Lighthouse → check "Progressive Web App" category → Generate report (mobile, default settings).

Expected:
- "Installable" passes.
- "PWA Optimized" passes (or only fails on splash-screen / themed-omnibox warnings, which are acceptable per spec).

- [ ] **Step 3: Install from production URL**

Repeat Task 5 steps 3 and 4 against the deployed URL (not `localhost`). Expected: install succeeds on both Android Chrome and iOS Safari, app loads, dashboard works.

- [ ] **Step 4: No commit**

Verification only.

---

## Acceptance Criteria (from spec)

After all tasks complete, confirm each box:

- [ ] `npm run build` succeeds and emits `manifest.webmanifest` + `sw.js` in `dist/` (Task 3 step 4)
- [ ] `npm run typecheck` passes (Task 3 step 3)
- [ ] Lighthouse PWA audit on the deployed Cloudflare Pages URL passes "Installable" criteria (Task 6 step 2)
- [ ] App is installable on Android Chrome via the browser-native prompt (Task 5 step 3, Task 6 step 3)
- [ ] App is installable on iOS Safari via Share → Add to Home Screen (Task 5 step 4, Task 6 step 3)
- [ ] Installed app opens full-screen (no browser chrome) and loads the connect/dashboard pages (Task 5 step 3/4)
- [ ] API calls from the installed app reach the prod backend successfully (Task 5 step 5, Task 6 step 3)
