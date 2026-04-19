import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { Link } from "react-router-dom"
import { useRef } from "react"

const BG =
  "https://images.unsplash.com/photo-1519681393784-d1202679338e?auto=format&fit=crop&w=1920&q=80"
const MID =
  "https://images.unsplash.com/photo-1552674605-469523167195?auto=format&fit=crop&w=1600&q=80"

function PhoneMock() {
  const path =
    "M 8 120 L 32 95 L 56 108 L 80 72 L 104 88 L 128 52 L 152 68 L 176 40 L 200 55 L 224 35 L 248 48 L 272 28 L 296 42 L 320 22 L 344 38 L 360 30"

  return (
    <div className="relative mx-auto w-[min(100%,280px)] rounded-[2rem] border border-brand-teal/40 bg-brand-charcoal/90 p-3 shadow-[0_0_60px_rgba(0,255,209,0.22),inset_0_1px_0_rgba(255,255,255,0.06)]">
      <div className="mb-2 flex items-center justify-between px-2 font-mono text-[9px] text-brand-muted">
        <span>VMM 160</span>
        <span className="text-brand-teal">+9,420 m</span>
      </div>
      <div className="relative h-[140px] w-full overflow-hidden rounded-xl bg-black/50">
        <svg className="h-full w-full" preserveAspectRatio="none" viewBox="0 0 360 140">
          <defs>
            <linearGradient id="heroElevGrad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#00ffd1" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#00ffd1" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={`${path} L 360 140 L 0 140 Z`} fill="url(#heroElevGrad)" opacity="0.5" />
          <motion.path
            animate={{ opacity: [0.7, 1, 0.7] }}
            d={path}
            fill="none"
            stroke="#00ffd1"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2.5"
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          />
        </svg>
        <p className="absolute bottom-2 left-2 font-mono text-[9px] text-brand-muted">elev profile · km 0–160</p>
      </div>
    </div>
  )
}

export default function HeroParallax() {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
  const y0 = useTransform(scrollYProgress, [0, 1], reduce ? [0, 0] : [0, "12%"])
  const y1 = useTransform(scrollYProgress, [0, 1], reduce ? [0, 0] : [0, "22%"])
  const y2 = useTransform(scrollYProgress, [0, 1], reduce ? [0, 0] : [0, "35%"])
  const opacityBg = useTransform(scrollYProgress, [0, 0.7], [1, 0.45])

  return (
    <section className="relative min-h-screen overflow-hidden bg-brand-void" ref={ref}>
      <motion.div className="absolute inset-0 scale-110" style={{ y: y0 }}>
        <img
          alt=""
          className="h-full w-full object-cover opacity-55"
          decoding="async"
          src={BG}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-brand-void/40 via-brand-void/70 to-brand-void" />
      </motion.div>

      <motion.div className="pointer-events-none absolute inset-0 mix-blend-screen" style={{ opacity: opacityBg, y: y1 }}>
        <img
          alt=""
          className="h-full w-full object-cover opacity-35"
          decoding="async"
          src={MID}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-brand-void via-transparent to-brand-void/80" />
      </motion.div>

      <motion.div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col justify-end gap-10 px-4 pb-20 pt-28 md:flex-row md:items-end md:justify-between md:pb-24" style={{ y: y2 }}>
        <div className="max-w-xl">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.35em] text-brand-teal">
            Decode the suffering
          </p>
          <h1 className="mt-4 text-4xl font-extrabold leading-[1.05] tracking-tight text-white md:text-6xl md:leading-[1.02]">
            STOP TRACKING.
            <br />
            START DIAGNOSING.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-brand-muted md:text-lg">
            The first AI Coach that understands hallucinations, vert debt, and the grit of 100 miles. Built for the
            mountains of SEA.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link
              className="inline-flex items-center justify-center rounded-full border border-white/25 bg-white/[0.08] px-8 py-3.5 text-sm font-bold uppercase tracking-wide text-white shadow-[0_8px_40px_rgba(0,0,0,0.45)] backdrop-blur-md transition hover:border-brand-teal/60 hover:bg-brand-teal/15 hover:text-brand-teal"
              to="/connect"
            >
              Connect Strava — It&apos;s Free
            </Link>
            <span className="font-mono text-[11px] text-brand-muted">No spam. Strava OAuth only.</span>
          </div>
        </div>
        <div className="relative w-full max-w-sm shrink-0 md:mb-0">
          <div className="absolute -inset-6 rounded-full bg-brand-teal/5 blur-3xl" />
          <PhoneMock />
        </div>
      </motion.div>
    </section>
  )
}
