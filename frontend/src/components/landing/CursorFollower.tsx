import { AnimatePresence, motion, useMotionValue, useSpring } from "framer-motion"
import { useEffect, useState } from "react"

export default function CursorFollower() {
  const [enabled, setEnabled] = useState(false)
  const [hoverMetric, setHoverMetric] = useState(false)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 280, damping: 28 })
  const sy = useSpring(y, { stiffness: 280, damping: 28 })

  useEffect(() => {
    setEnabled(window.matchMedia("(pointer: fine)").matches)
  }, [])

  useEffect(() => {
    if (!enabled) return
    function onMove(e: MouseEvent) {
      x.set(e.clientX)
      y.set(e.clientY)
    }
    window.addEventListener("mousemove", onMove)
    return () => window.removeEventListener("mousemove", onMove)
  }, [enabled, x, y])

  useEffect(() => {
    if (!enabled) return
    function onOver(e: MouseEvent) {
      const t = e.target as HTMLElement | null
      setHoverMetric(!!t?.closest?.("[data-metric-hover]"))
    }
    window.addEventListener("mouseover", onOver)
    return () => window.removeEventListener("mouseover", onOver)
  }, [enabled])

  if (!enabled) return null

  return (
    <motion.div
      aria-hidden
      className="pointer-events-none fixed left-0 top-0 z-[60] hidden md:block"
      style={{ x: sx, y: sy }}
    >
      <div className="-translate-x-1/2 -translate-y-1/2">
        <AnimatePresence mode="wait">
          {hoverMetric ? (
            <motion.span
              animate={{ opacity: 1, scale: 1 }}
              className="inline-flex items-center gap-1 rounded-full border border-brand-teal/50 bg-brand-void/90 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-brand-teal shadow-[0_0_24px_rgba(0,255,209,0.25)]"
              exit={{ opacity: 0, scale: 0.85 }}
              initial={{ opacity: 0, scale: 0.85 }}
              key="label"
              transition={{ duration: 0.15 }}
            >
              <span aria-hidden>🔍</span> Deep Dive
            </motion.span>
          ) : (
            <motion.span
              animate={{ opacity: 1, scale: 1 }}
              className="block h-2.5 w-2.5 rounded-full bg-brand-teal shadow-[0_0_12px_rgba(0,255,209,0.9)]"
              exit={{ opacity: 0, scale: 0.5 }}
              initial={{ opacity: 0.6, scale: 0.8 }}
              key="dot"
              transition={{ duration: 0.12 }}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}
