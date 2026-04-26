# PWA — Installable Frontend

**Date:** 2026-04-26
**Status:** Approved (design phase)
**Scope:** `frontend/` only

---

## Goal

Make the Strava Coach frontend installable on iOS Safari and Android Chrome so it lives on the home screen and opens full-screen like a native app.

## In scope

- Web app manifest (name, icons, theme, display mode)
- Minimal service worker — required for installability; precaches the built JS/CSS so the app shell loads instantly and survives flaky networks
- Icons: 192×192, 512×512, 512×512 maskable (Android adaptive), 180×180 (iOS)
- Generated from a 🏔️ emoji centered on a solid `#050505` background (matches `brand.void` from `tailwind.config.ts`)
- iOS-specific meta tags so Safari treats it as a real app
- Build integrated into existing Vite pipeline; deploys via current Cloudflare Pages flow with no extra steps

## Out of scope

- Offline API caching — every API call still requires internet
- Push notifications (Telegram is on the roadmap separately)
- App store distribution (TWA / Capacitor)
- iOS `apple-touch-startup-image` splash screens — iOS will fall back to a black background, which matches the theme

## Non-goals (deliberately not changing)

- Any page, component, hook, store, or API client
- Backend (already deployed to prod)
- Cloudflare Pages config (`_headers`, `_redirects`)
- Existing test suite

---

## Approach

Use **`vite-plugin-pwa` with `generateSW`**.

It's the standard choice for Vite. Generates the manifest, generates a Workbox-based service worker, injects registration code, and supports dev-mode HMR.

**Alternatives rejected:**

| Option | Rejected because |
|---|---|
| Hand-rolled SW + manifest | Re-implements cache-busting on every build. Not worth it. |
| `vite-plugin-pwa` with `injectManifest` (write own SW) | Only useful if custom caching logic is needed. Default precache-everything behavior is exactly what option A wants. |
| No service worker, just a manifest | Android Chrome would install, but iOS Safari would not show "Add to Home Screen" as a real PWA. Loses offline app-shell loading. Cost of including the SW is ~1 KB of plugin config. |

---

## File changes

```
frontend/
├── package.json                          ← add vite-plugin-pwa
├── vite.config.ts                        ← register plugin with manifest config
├── index.html                            ← add iOS meta tags + theme-color
├── scripts/
│   └── generate-icons.mjs                NEW — one-shot icon generator
└── public/
    ├── icon-192.png                      NEW — 192×192
    ├── icon-512.png                      NEW — 512×512
    ├── icon-512-maskable.png             NEW — 512×512 with safe-zone padding
    └── apple-touch-icon.png              NEW — 180×180 for iOS
```

No changes to `src/main.tsx` — `vite-plugin-pwa` auto-injects SW registration into `index.html` when `injectRegister: "auto"` (the default).

---

## Manifest config (in `vite.config.ts`)

```ts
VitePWA({
  registerType: "autoUpdate",
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
  },
})
```

**Color rationale:** `#050505` is `brand.void` from `tailwind.config.ts` — already the background of the dark theme. Status bar and launch flash will match.

---

## Service worker behavior (Workbox `generateSW` defaults)

- **Precache the build output** — `index.html`, all hashed JS/CSS chunks, fonts. Updated on every deploy via the file hashes Vite already produces.
- **Network-first for `index.html`** — so a new deploy is picked up on next launch.
- **Cache-first for hashed assets** — they're immutable, so this is safe.
- **No API caching.** API calls (`/dashboard/load`, `/debrief`, etc.) bypass the SW entirely and go straight to the network. This matches scope: no offline data.

**Update flow:** `skipWaiting: true` + `clientsClaim: true` = new version applies on the next cold launch from the home screen. No in-app toast, no extra code.

---

## iOS specifics

iOS Safari ignores most of the manifest, so add these to `index.html`:

```html
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Coach" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<meta name="theme-color" content="#050505" />
```

**Install flow on iOS:** Share → Add to Home Screen. There's no install prompt like Android — this is iOS behavior and can't be changed.

**Known iOS limitations (acknowledged, not addressed):**
- No background sync; push notifications limited (out of scope)
- Service worker storage capped ~50 MB (we're far under)
- No splash screens generated — falls back to black background, matches theme

---

## Icon generation

`frontend/scripts/generate-icons.mjs` — a one-shot Node script (not part of the build) that renders 🏔️ centered on a solid `#050505` background and writes the four PNGs to `public/`.

**Implementation:** uses `playwright` (already in `devDependencies`) — launches a headless Chromium, renders a tiny HTML page with the emoji styled at the right size on the background color, and screenshots it as PNG. Avoids native-build issues that plague `canvas` and `sharp` on some macOS setups. Run once with `node scripts/generate-icons.mjs`. Output is committed to git so `public/` works for any developer.

**Maskable variant:** same emoji, rendered with ~20% padding on all sides so the system's circle/squircle crop on Android doesn't clip the mountain.

If the user later wants a different icon, edit the script (change emoji or color) and re-run. Trivial to swap.

---

## Testing

**Build-time:**
- `npm run build` produces `dist/manifest.webmanifest`, `dist/sw.js`, and the four icon PNGs in `dist/`.
- `npm run typecheck` still passes (plugin ships TS types).

**Manual smoke (one-time, by user):**
1. `npm run build && npm run preview` → open on phone via LAN URL
2. Chrome on Android: install prompt appears → install → icon on home screen → opens full-screen
3. Safari on iOS: Share → Add to Home Screen → icon appears → opens full-screen
4. Open installed app while on prod backend → dashboard loads

**No new automated tests.** PWA install behavior is browser-specific and not meaningfully unit-testable; existing tests already cover app logic.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Cached old version after deploy | `skipWaiting` + `clientsClaim` + `registerType: "autoUpdate"` — new version applies on next cold launch |
| Maskable icon clipped on Android | 20% safe-zone padding in the generator script |
| Emoji renders inconsistently across systems | Use Playwright headless Chromium (already a dep) — same render everywhere; script is idempotent and not in the build pipeline |
| iOS install flow confusion (no prompt) | Document the Share → Add to Home Screen flow in the implementation plan |

---

## Acceptance criteria

- [ ] `npm run build` succeeds and emits `manifest.webmanifest` + `sw.js` in `dist/`
- [ ] `npm run typecheck` passes
- [ ] Lighthouse PWA audit on the deployed Cloudflare Pages URL passes "Installable" criteria
- [ ] App is installable on Android Chrome via the browser-native prompt
- [ ] App is installable on iOS Safari via Share → Add to Home Screen
- [ ] Installed app opens full-screen (no browser chrome) and loads the connect/dashboard pages
- [ ] API calls from the installed app reach the prod backend successfully
