import Lenis from "lenis"
import { useEffect } from "react"

export function useLenis(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return
    const lenis = new Lenis({
      // Snappier than defaults: shorter glide, stronger wheel steps, higher lerp = less “float”
      duration: 0.5,
      lerp: 0.22,
      smoothWheel: true,
      wheelMultiplier: 1.5,
      touchMultiplier: 1.35,
    })
    let raf = 0
    function tick(time: number) {
      lenis.raf(time)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      lenis.destroy()
    }
  }, [enabled])
}
