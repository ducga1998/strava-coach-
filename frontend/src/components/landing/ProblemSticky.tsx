import { motion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"

export default function ProblemSticky() {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] })
  const a = useTransform(scrollYProgress, [0.15, 0.42], [1, 0])
  const b = useTransform(scrollYProgress, [0.38, 0.62], [0, 1])
  const aY = useTransform(scrollYProgress, [0.15, 0.42], [0, -14])
  const bY = useTransform(scrollYProgress, [0.38, 0.62], [14, 0])

  return (
    <div className="bg-brand-void" ref={ref}>
      <div className="relative h-[220vh]">
        <div className="sticky top-0 flex h-screen items-center justify-center px-4">
          <div className="relative mx-auto min-h-[200px] w-full max-w-4xl text-center md:min-h-[140px]">
            <motion.p
              className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-2xl font-semibold leading-snug text-white md:text-4xl md:leading-tight"
              style={{ opacity: a, y: aY }}
            >
              Strava tells you that you ran. We tell you{" "}
              <span className="text-brand-teal">why you felt like dying.</span>
            </motion.p>
            <motion.p
              className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-2xl font-semibold leading-snug text-white md:text-4xl md:leading-tight"
              style={{ opacity: b, y: bY }}
            >
              Generic apps give you a &apos;Good Job&apos;. We give you a{" "}
              <span className="text-brand-lime">medical-grade recovery plan.</span>
            </motion.p>
          </div>
        </div>
      </div>
    </div>
  )
}
