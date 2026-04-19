import { useLayoutEffect } from "react"

/** Match marketing home: document background + foreground for overscroll and body. */
export function useDarkPageChrome() {
  useLayoutEffect(() => {
    const el = document.documentElement
    el.style.setProperty("--page-bg", "#050505")
    el.style.setProperty("--page-fg", "#f8fafc")
    el.style.colorScheme = "dark"
    return () => {
      el.style.removeProperty("--page-bg")
      el.style.removeProperty("--page-fg")
      el.style.removeProperty("color-scheme")
    }
  }, [])
}
